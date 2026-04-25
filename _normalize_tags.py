"""
Normalize stray tags in the FuckCars vault.

Haiku 4.5 produced ~40 tag instances outside our taxonomy despite the
enum constraint. This script remaps known aliases to canonical tags and
drops genuine outliers. Pure local file edit — no API calls.

Idempotent: safe to run multiple times.
"""

import re
from pathlib import Path

VAULT = Path(r"C:\Users\Etien\OneDrive\Documents\Obsidian Vaults\FuckCars Vault")
POSTS = VAULT / "posts"

# stray tag -> canonical tag (or None to drop)
TAG_MAP = {
    # alias variants
    "walkability": "walking",
    "pedestrians": "walking",
    "cars-culture": "car-culture",
    "traffic": "cars",
    "advocacy": "policy",
    "political-commentary": "policy",
    "nimbyism": "housing",
    "density": "housing",
    "commentary": "news-commentary",
    "traffic-calming": "street-design",
    "stroads": "highways",
    "transit-oriented": "public-transit",
    "paris": "europe",
    # genuine outliers with no good taxonomy fit — drop
    "history": None,
    "health": None,
    "sarcasm": None,
    "children-welfare": None,
    "children": None,
    "australia": None,
    "asia": None,
    "south-america": None,
}


def parse_frontmatter(text):
    if not text.startswith("---\n"):
        return None, text
    end = text.find("\n---\n", 4)
    if end < 0:
        return None, text
    return text[4:end], text[end + 5:]


def normalize_tags(fm_text):
    lines = fm_text.split("\n")
    out = []
    n_changes = 0
    in_block = False
    block_tags = []

    def flush_block():
        nonlocal n_changes
        new = []
        for t in block_tags:
            if t in TAG_MAP:
                replacement = TAG_MAP[t]
                if replacement is not None:
                    new.append(replacement)
                n_changes += 1
            else:
                new.append(t)
        new = sorted(set(new))
        if new:
            out.append("tags:")
            for t in new:
                out.append(f"  - {t}")

    for line in lines:
        if line.startswith("tags:"):
            in_block = True
            block_tags = []
            continue
        if in_block:
            m = re.match(r"^  - (.+)$", line)
            if m:
                block_tags.append(m.group(1).strip())
                continue
            else:
                flush_block()
                in_block = False
                out.append(line)
                continue
        out.append(line)

    if in_block:
        flush_block()

    return "\n".join(out), n_changes


def main():
    notes = sorted(POSTS.rglob("*.md"))
    total_changes = 0
    files_changed = 0
    print(f"Scanning {len(notes)} notes...")

    for path in notes:
        text = path.read_text(encoding="utf-8")
        fm_text, body = parse_frontmatter(text)
        if fm_text is None:
            continue
        new_fm, n = normalize_tags(fm_text)
        if n > 0:
            path.write_text(f"---\n{new_fm}\n---\n{body}", encoding="utf-8")
            files_changed += 1
            total_changes += n

    print(f"Done. {total_changes} tag changes across {files_changed} files.")


if __name__ == "__main__":
    main()
