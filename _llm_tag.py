"""
LLM topical tagging pass for the FuckCars vault.

Reads each note in posts/, sends body text to Claude Haiku 4.5,
and rewrites the frontmatter `tags:` field with cleaner topical tags.

Preserves structural tags (has-media, viral, thread, image, etc.) and
original `hashtag-*` tags. Replaces only the keyword-derived topical tags.

Idempotent: notes already tagged are skipped (marked with `llm_tagged:` in
frontmatter). Resumable: if interrupted, just re-run.

Setup:
  1. pip install anthropic
  2. set ANTHROPIC_API_KEY env var (see setup notes)

Usage:
  python _llm_tag.py --limit 5      # test on 5 notes first
  python _llm_tag.py                # full run
  python _llm_tag.py --retag        # force re-tag everything

Estimated cost on Haiku 4.5 with prompt caching: ~$0.40-0.80 for 1180 notes.
"""

import argparse
import os
import re
import sys
import time
from pathlib import Path

try:
    from anthropic import Anthropic
    from anthropic import APIError, RateLimitError
except ImportError:
    sys.exit("anthropic SDK not installed. Run: pip install anthropic")


VAULT = Path(r"C:\Users\Etien\OneDrive\Documents\Obsidian Vaults\FuckCars Vault")
POSTS = VAULT / "posts"

MODEL = "claude-haiku-4-5"

# Topical tags the LLM is allowed to use. Keep this list curated and stable —
# changing it later means re-running the pass to get consistent results.
ALLOWED_TAGS = [
    "cars",                # cars, drivers, traffic congestion, SUVs/trucks as a topic
    "parking",             # parking lots, garages, parking minimums
    "public-transit",      # buses, trains, subway, metro, rail, BRT
    "bikes",               # cycling, bike lanes, e-bikes
    "walking",             # pedestrians, sidewalks, walkability
    "housing",             # housing supply, density, apartments, missing middle
    "zoning",              # zoning laws, land use, single-family-only zoning
    "sprawl",              # suburbs, exurbs, low-density development
    "highways",            # freeways, interstates, stroads, big arterials
    "street-design",       # intersections, lane width, complete streets, traffic calming
    "safety",              # crashes, fatalities, traffic violence, vision zero
    "climate",             # emissions, pollution, EVs as a topic
    "urbanism",            # general city/urban planning theory
    "policy",              # laws, votes, advocacy, government decisions
    "car-culture",         # critique of car culture, advertising, ads, lifestyle
    "infrastructure",      # roads, bridges, maintenance, costs
    "north-america",       # specifically US/Canada-focused content
    "europe",              # specifically Europe-focused content
    "data-chart",          # post centers on a chart, graph, map, or statistic
    "humor-meme",          # clearly a meme/joke post (not just any sarcasm)
    "personal-anecdote",   # first-person experience or story
    "news-commentary",     # reacting to a news article or current event
]

# Structural tags from _convert.py — these survive the LLM pass.
STRUCTURAL_TAGS = {
    "has-media", "image", "video", "gif", "thread",
    "mega-viral", "viral", "popular",
}

SYSTEM_PROMPT = """You are tagging posts from an urbanist Twitter account
(@FuckCarsReddit) focused on car-criticism, urbanist commentary, and memes.

Tag each post with the applicable topical tags from this fixed list:

- cars: cars, drivers, traffic congestion, SUVs/trucks as a topic
- parking: parking lots, garages, parking minimums
- public-transit: buses, trains, subway, metro, rail, BRT
- bikes: cycling, bike lanes, e-bikes
- walking: pedestrians, sidewalks, walkability
- housing: housing supply, density, apartments, missing middle
- zoning: zoning laws, land use, single-family-only zoning
- sprawl: suburbs, exurbs, low-density development
- highways: freeways, interstates, stroads, big arterials
- street-design: intersections, lane width, complete streets, traffic calming
- safety: crashes, fatalities, traffic violence, vision zero
- climate: emissions, pollution, EVs as a topic
- urbanism: general city/urban planning theory
- policy: laws, votes, advocacy, government decisions
- car-culture: critique of car culture, advertising, ads, lifestyle
- infrastructure: roads, bridges, maintenance, costs
- north-america: specifically US/Canada-focused content
- europe: specifically Europe-focused content
- data-chart: post is built around an actual chart, graph, plotted map, or numeric statistic
- humor-meme: clearly a meme/joke post (not just any sarcasm)
- personal-anecdote: first-person experience or story
- news-commentary: reacting to a news article or current event

Rules:
- Use only tags from the list above. Do not invent tags.
- Most posts get 1-3 tags. Some get 0 (random shitpost, off-topic banter).
- Don't reflexively tag every post with `cars` just because the account is anti-car.
  Only use `cars` when the post is specifically about cars/driving/traffic.
- `humor-meme` is for clear memes/jokes, not for any post with sarcasm.
- `data-chart` is ONLY for posts whose primary content is a chart, graph, plotted map,
  or explicit numeric statistic. Do NOT use it for before/after photo comparisons,
  side-by-side photo comparisons, satellite/aerial photos without overlaid data,
  or simple street photos. If the post would still make sense as just words, it's
  probably not data-chart.
- `north-america` / `europe` only when a specific place in the region is named or clearly implied.
- If unsure, prefer fewer tags over more. Better to miss a tag than misclassify.

Return tags via the `tag_post` tool.
"""

TAG_TOOL = {
    "name": "tag_post",
    "description": "Submit topical tags for a post.",
    "input_schema": {
        "type": "object",
        "properties": {
            "tags": {
                "type": "array",
                "items": {"type": "string", "enum": ALLOWED_TAGS},
                "description": "Applicable tags from the allowed list. Empty list if none apply.",
            }
        },
        "required": ["tags"],
    },
}


def parse_frontmatter(text):
    if not text.startswith("---\n"):
        return None, text
    end = text.find("\n---\n", 4)
    if end < 0:
        return None, text
    return text[4:end], text[end + 5:]


def get_existing_tags(fm_text):
    tags = []
    in_block = False
    for line in fm_text.split("\n"):
        if line.startswith("tags:"):
            in_block = True
            continue
        if in_block:
            m = re.match(r"^  - (.+)$", line)
            if m:
                tags.append(m.group(1).strip())
            else:
                in_block = False
    return tags


def is_already_tagged(fm_text):
    return bool(re.search(r"^llm_tagged:", fm_text, re.MULTILINE))


def rewrite_frontmatter(fm_text, new_tags):
    """Drop the existing tags: block and llm_tagged line, append new ones."""
    lines = fm_text.split("\n")
    out = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("tags:"):
            i += 1
            while i < len(lines) and lines[i].startswith("  - "):
                i += 1
            continue
        if line.startswith("llm_tagged:"):
            i += 1
            continue
        out.append(line)
        i += 1
    while out and not out[-1].strip():
        out.pop()
    if new_tags:
        out.append("tags:")
        for t in sorted(new_tags):
            out.append(f"  - {t}")
    out.append(f"llm_tagged: {time.strftime('%Y-%m-%d')}")
    return "\n".join(out)


def extract_post_text(body):
    """Strip media embeds, footer, thread headings, and per-tweet stats from
    the body so the LLM only sees the actual tweet text."""
    text = body
    text = re.sub(r"!\[\[.*?\]\]", "", text)
    parts = text.rsplit("\n---\n", 1)
    if len(parts) == 2:
        text = parts[0]
    text = re.sub(r"^## \d+/\d+\s*$", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\*❤.*$", "", text, flags=re.MULTILINE)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return text


def classify_with_retry(client, post_text, max_retries=3):
    for attempt in range(max_retries):
        try:
            msg = client.messages.create(
                model=MODEL,
                max_tokens=200,
                system=[
                    {
                        "type": "text",
                        "text": SYSTEM_PROMPT,
                        "cache_control": {"type": "ephemeral"},
                    }
                ],
                tools=[TAG_TOOL],
                tool_choice={"type": "tool", "name": "tag_post"},
                messages=[{"role": "user", "content": post_text}],
            )
            for block in msg.content:
                if block.type == "tool_use" and block.name == "tag_post":
                    return block.input.get("tags", []), msg.usage
            return [], msg.usage
        except RateLimitError:
            wait = 2 ** attempt * 5
            print(f"  rate-limited, sleeping {wait}s")
            time.sleep(wait)
        except APIError as e:
            if attempt == max_retries - 1:
                raise
            wait = 2 ** attempt * 2
            print(f"  api error ({e}), sleeping {wait}s")
            time.sleep(wait)
    raise RuntimeError("exhausted retries")


def estimate_cost(in_tokens, cached_read, cache_create, out_tokens):
    # Haiku 4.5 pricing per million tokens:
    # input $1.00 · cache write $1.25 · cache read $0.10 · output $5.00
    return (
        in_tokens * 1.00
        + cache_create * 1.25
        + cached_read * 0.10
        + out_tokens * 5.00
    ) / 1_000_000


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None,
                        help="Only process the first N notes (for testing)")
    parser.add_argument("--retag", action="store_true",
                        help="Re-tag notes that have already been LLM-tagged")
    args = parser.parse_args()

    if not os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit(
            "ANTHROPIC_API_KEY env var is not set.\n"
            "Set it with:  setx ANTHROPIC_API_KEY \"sk-ant-...\"\n"
            "then close and reopen your terminal."
        )

    if not POSTS.exists():
        sys.exit(f"posts/ folder not found at: {POSTS}")

    client = Anthropic()
    notes = sorted(POSTS.rglob("*.md"))
    if args.limit:
        notes = notes[: args.limit]
    print(f"Vault: {VAULT}")
    print(f"Notes to consider: {len(notes)}")
    print(f"Model: {MODEL}")
    print()

    total_in = total_cached = total_create = total_out = 0
    processed = skipped = errored = 0

    for i, path in enumerate(notes, 1):
        text = path.read_text(encoding="utf-8")
        fm_text, body = parse_frontmatter(text)

        if fm_text is None:
            skipped += 1
            continue

        if is_already_tagged(fm_text) and not args.retag:
            skipped += 1
            continue

        post_text = extract_post_text(body)
        if not post_text.strip():
            # nothing to classify — keep existing tags, just mark as processed
            existing = get_existing_tags(fm_text)
            new_fm = rewrite_frontmatter(fm_text, existing)
            path.write_text(f"---\n{new_fm}\n---\n\n{body}", encoding="utf-8")
            skipped += 1
            continue

        try:
            llm_tags, usage = classify_with_retry(client, post_text)
        except Exception as e:
            print(f"[{i}/{len(notes)}] ERROR on {path.name}: {e}")
            errored += 1
            continue

        existing = get_existing_tags(fm_text)
        preserved = [
            t for t in existing
            if t in STRUCTURAL_TAGS or t.startswith("hashtag-")
        ]
        final_tags = sorted(set(preserved) | set(llm_tags))

        new_fm = rewrite_frontmatter(fm_text, final_tags)
        path.write_text(f"---\n{new_fm}\n---\n\n{body}", encoding="utf-8")

        total_in += usage.input_tokens
        total_out += usage.output_tokens
        total_cached += getattr(usage, "cache_read_input_tokens", 0) or 0
        total_create += getattr(usage, "cache_creation_input_tokens", 0) or 0
        processed += 1

        if processed % 25 == 0 or i == len(notes):
            cost = estimate_cost(total_in, total_cached, total_create, total_out)
            print(f"[{i}/{len(notes)}] processed={processed} skipped={skipped} "
                  f"errored={errored} | running cost: ${cost:.3f}")

    print()
    print(f"Done. processed={processed} skipped={skipped} errored={errored}")
    print(f"Tokens: input={total_in} cache_read={total_cached} "
          f"cache_create={total_create} output={total_out}")
    cost = estimate_cost(total_in, total_cached, total_create, total_out)
    print(f"Estimated cost: ${cost:.3f}")


if __name__ == "__main__":
    main()
