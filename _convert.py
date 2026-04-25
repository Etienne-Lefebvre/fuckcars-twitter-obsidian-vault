"""
Convert a Twitter archive to an Obsidian vault.

Filters: keeps original tweets and self-threads only.
Tagging: structural tags + urbanist keyword tags.
"""

import json
import re
import shutil
import html
from pathlib import Path
from collections import defaultdict
from datetime import datetime

ARCHIVE = Path(r"c:/Users/Etien/Downloads/twitter-2026-04-25-967d31b639a279d60f41a0a78b93b6c739594fe55fd319c579c7db783b50c2d0")
VAULT = Path(r"c:/Users/Etien/Downloads/FuckCars-Vault")
POSTS = VAULT / "posts"
ATTACH = VAULT / "attachments"
USERNAME = "FuckCarsReddit"
USER_ID = "1474392309915602951"


# ---------- urbanist keyword tagging ----------
# Each entry: tag -> list of regex patterns (case-insensitive, word-boundary aware).
KEYWORD_TAGS = {
    "cars": [r"\bcars?\b", r"\bautomobiles?\b", r"\bdriving\b", r"\bdrivers?\b",
             r"\bsuvs?\b", r"\btrucks?\b", r"\btraffic\b", r"\bcarbrain\b"],
    "parking": [r"\bparking\b", r"\bparking lots?\b", r"\bparking minimums?\b",
                r"\bgarages?\b", r"\bparking craters?\b"],
    "transit": [r"\btransit\b", r"\bbuses?\b", r"\bsubways?\b", r"\bmetros?\b",
                r"\btrains?\b", r"\brail\b", r"\blight.rail\b", r"\bstreetcars?\b",
                r"\btrams?\b", r"\bhsr\b", r"\bhigh.speed rail\b", r"\bamtrak\b",
                r"\bbrt\b", r"\bbus rapid transit\b", r"\bcaltrain\b", r"\bmta\b"],
    "bikes": [r"\bbikes?\b", r"\bbicycles?\b", r"\bcycling\b", r"\bcyclists?\b",
              r"\be.bikes?\b", r"\bbike lanes?\b", r"\bbike paths?\b"],
    "walking": [r"\bpedestrians?\b", r"\bwalking\b", r"\bwalkable\b",
                r"\bwalkability\b", r"\bsidewalks?\b", r"\bcrosswalks?\b",
                r"\bjaywalk\w*\b"],
    "housing": [r"\bhousing\b", r"\bapartments?\b", r"\bcondos?\b",
                r"\bnimby\w*\b", r"\byimby\w*\b", r"\bdensity\b", r"\bdense\b",
                r"\bmissing middle\b", r"\bsfh\b", r"\bsingle.family\b",
                r"\brents?\b", r"\baffordable\b", r"\bduplex(es)?\b",
                r"\btriplex(es)?\b", r"\bfourplex(es)?\b"],
    "zoning": [r"\bzoning\b", r"\bzoned\b", r"\bzoning code\b",
               r"\beuclidean zoning\b", r"\bupzoning\b", r"\bdownzoning\b"],
    "sprawl": [r"\bsprawl\b", r"\bsuburbs?\b", r"\bsuburbia\b", r"\bsuburban\b",
               r"\bexurbs?\b", r"\bcul.de.sac\b", r"\bsubdivisions?\b"],
    "highways": [r"\bhighways?\b", r"\bfreeways?\b", r"\binterstates?\b",
                 r"\bexpressways?\b", r"\bstroads?\b", r"\bovervpass(es)?\b",
                 r"\boff.ramps?\b", r"\bon.ramps?\b"],
    "streets": [r"\bstreet design\b", r"\bcomplete streets\b",
                r"\bintersections?\b", r"\broundabouts?\b", r"\btraffic calming\b",
                r"\broad diet\b", r"\blane diet\b"],
    "safety": [r"\bcrash(es)?\b", r"\bcollisions?\b", r"\baccidents?\b",
               r"\bfatalit\w+\b", r"\bvision zero\b", r"\btraffic violence\b",
               r"\bhit.and.run\b", r"\brun over\b", r"\brun.over\b", r"\bkilled by\b"],
    "climate": [r"\bclimate\b", r"\bemissions?\b", r"\bpollution\b",
                r"\bgreenhouse\b", r"\bcarbon\b", r"\bevs?\b",
                r"\belectric vehicles?\b", r"\btesla\b"],
    "urbanism": [r"\burbanis[mt]\b", r"\burban planning\b", r"\bcity planning\b",
                 r"\bdowntown\b", r"\bmain street\b", r"\bmixed.use\b",
                 r"\b15.minute\b", r"\bnew urbanis[mt]\b"],
    "europe": [r"\bnetherlands\b", r"\bdutch\b", r"\bamsterdam\b", r"\butrecht\b",
               r"\bcopenhagen\b", r"\bdenmark\b", r"\bparis\b", r"\bfrance\b",
               r"\bgermany\b", r"\bberlin\b", r"\bspain\b", r"\bbarcelona\b",
               r"\bsuperblock\w*\b", r"\beurope\w*\b"],
    "north-america": [r"\busa\b", r"\bamerica\w*\b", r"\bcanada\b", r"\btoronto\b",
                      r"\bmontreal\b", r"\bvancouver\b", r"\bnyc\b", r"\bnew york\b",
                      r"\blos angeles\b", r"\bla\b", r"\bhouston\b", r"\bdallas\b",
                      r"\bphoenix\b", r"\bdetroit\b", r"\bchicago\b", r"\bsf\b",
                      r"\bsan francisco\b"],
    "memes": [r"\bmeme\b", r"\bbased\b", r"\bcope\b", r"\bratio\b",
              r"\btouch grass\b"],
    "reddit": [r"\breddit\b", r"\br/\w+\b", r"\bsubreddit\b"],
}

COMPILED_KEYWORDS = {tag: [re.compile(p, re.IGNORECASE) for p in pats]
                     for tag, pats in KEYWORD_TAGS.items()}


def parse_js(path: Path):
    text = path.read_text(encoding="utf-8")
    # strip "window.YTD.X.partN = " prefix
    text = re.sub(r"^window\.YTD\.[a-zA-Z_]+\.part\d+\s*=\s*", "", text, count=1)
    return json.loads(text)


def is_retweet(t):
    return t.get("full_text", "").startswith("RT @")


def is_reply_to_other(t):
    target = t.get("in_reply_to_user_id_str") or t.get("in_reply_to_user_id")
    return target is not None and target != USER_ID


def expand_urls(text, urls):
    """Replace t.co URLs with their expanded form. Drop t.co URLs that
    point at media (those get embedded separately)."""
    for u in urls or []:
        text = text.replace(u["url"], u["expanded_url"])
    return text


def strip_media_urls(text, media_list):
    for m in media_list or []:
        text = text.replace(m["url"], "")
    return text


def slugify(text, max_len=50):
    text = html.unescape(text)
    text = re.sub(r"https?://\S+", "", text)
    text = re.sub(r"[^a-zA-Z0-9\s]", "", text)
    text = re.sub(r"\s+", "-", text).strip("-").lower()
    return text[:max_len].rstrip("-") or "untitled"


def find_media_files(tweet_id):
    return sorted(ATTACH.parent.parent.glob("__none__"))  # placeholder, replaced below


def collect_keyword_tags(text):
    tags = []
    for tag, patterns in COMPILED_KEYWORDS.items():
        for p in patterns:
            if p.search(text):
                tags.append(tag)
                break
    return tags


def structural_tags(thread_tweets, total_likes, total_rts, has_image, has_video, has_gif):
    tags = []
    if len(thread_tweets) > 1:
        tags.append("thread")
    if has_image:
        tags.append("image")
    if has_video:
        tags.append("video")
    if has_gif:
        tags.append("gif")
    if has_image or has_video or has_gif:
        tags.append("has-media")
    if total_likes >= 10000:
        tags.append("mega-viral")
    elif total_likes >= 1000:
        tags.append("viral")
    elif total_likes >= 100:
        tags.append("popular")
    return tags


def main():
    tweets_raw = parse_js(ARCHIVE / "data" / "tweets.js")
    tweets = [item["tweet"] for item in tweets_raw]
    print(f"Total tweets in archive: {len(tweets)}")

    # filter
    survivors = []
    n_rt = n_reply = 0
    for t in tweets:
        if is_retweet(t):
            n_rt += 1
            continue
        if is_reply_to_other(t):
            n_reply += 1
            continue
        survivors.append(t)
    print(f"Filtered out {n_rt} retweets, {n_reply} replies-to-others.")
    print(f"Surviving tweets: {len(survivors)}")

    survivor_ids = {t["id_str"] for t in survivors}
    by_id = {t["id_str"]: t for t in survivors}

    # group into threads. parent = in_reply_to_status_id_str if it points
    # to another surviving tweet (i.e. self-reply). otherwise the tweet is a root.
    children = defaultdict(list)
    parents = {}
    for t in survivors:
        parent_id = t.get("in_reply_to_status_id_str")
        if parent_id and parent_id in survivor_ids:
            children[parent_id].append(t["id_str"])
            parents[t["id_str"]] = parent_id

    roots = [t for t in survivors if t["id_str"] not in parents]
    print(f"Thread roots: {len(roots)} (single tweets + thread starters)")

    # build chronologically-ordered thread members for each root
    threads = []
    for root in roots:
        members = []
        # BFS through children, then sort by date
        stack = [root["id_str"]]
        seen = set()
        while stack:
            cur = stack.pop()
            if cur in seen:
                continue
            seen.add(cur)
            members.append(by_id[cur])
            stack.extend(children.get(cur, []))
        members.sort(key=lambda t: parse_date(t["created_at"]))
        threads.append(members)

    print(f"Threads/notes to write: {len(threads)}")

    # build a map of tweet_id -> media file paths (in archive)
    tweets_media_dir = ARCHIVE / "data" / "tweets_media"
    media_files = list(tweets_media_dir.glob("*"))
    media_by_tweet = defaultdict(list)
    for f in media_files:
        # filename starts with tweet_id, then "-"
        m = re.match(r"^(\d+)-", f.name)
        if m:
            media_by_tweet[m.group(1)].append(f)

    written = 0
    media_copied = 0
    for thread in threads:
        n, copied = write_thread(thread, media_by_tweet)
        if n:
            written += 1
            media_copied += copied

    print(f"\nWrote {written} notes. Copied {media_copied} media files.")


def parse_date(s):
    # "Thu Jan 08 20:27:48 +0000 2026"
    return datetime.strptime(s, "%a %b %d %H:%M:%S %z %Y")


def render_tweet_body(t):
    """Return (text_with_expanded_urls, list_of_media_file_basenames_to_embed)."""
    text = t.get("full_text", "")
    entities = t.get("entities", {})
    text = expand_urls(text, entities.get("urls", []))
    text = strip_media_urls(text, entities.get("media", []))
    text = html.unescape(text)
    text = text.strip()
    return text


def write_thread(thread, media_by_tweet):
    root = thread[0]
    root_id = root["id_str"]
    created = parse_date(root["created_at"])
    year = str(created.year)
    out_dir = POSTS / year
    out_dir.mkdir(parents=True, exist_ok=True)

    # filename: YYYY-MM-DD_HHMM_<slug>.md, dedupe with id suffix if collision
    first_text = render_tweet_body(root)
    slug = slugify(first_text)
    fname_base = f"{created.strftime('%Y-%m-%d_%H%M')}_{slug}"
    fpath = out_dir / f"{fname_base}.md"
    if fpath.exists():
        fpath = out_dir / f"{fname_base}_{root_id[-6:]}.md"

    # gather aggregate stats
    total_likes = sum(int(t.get("favorite_count", 0)) for t in thread)
    total_rts = sum(int(t.get("retweet_count", 0)) for t in thread)
    root_likes = int(root.get("favorite_count", 0))
    root_rts = int(root.get("retweet_count", 0))

    # gather media + mentions across thread
    has_image = has_video = has_gif = False
    all_mentions = set()
    media_count = 0
    media_copied = 0
    for t in thread:
        ents = t.get("entities", {})
        ext_ents = t.get("extended_entities", {})
        media = ext_ents.get("media") or ents.get("media") or []
        media_count += len(media)
        for m in media:
            mtype = m.get("type", "photo")
            if mtype == "photo":
                has_image = True
            elif mtype == "video":
                has_video = True
            elif mtype == "animated_gif":
                has_gif = True
        for m in ents.get("user_mentions", []):
            sn = m.get("screen_name")
            if sn and sn.lower() != USERNAME.lower():
                all_mentions.add(sn)

    # build tag list
    full_text_concat = " ".join(render_tweet_body(t) for t in thread)
    tags = []
    tags += structural_tags(thread, total_likes, total_rts, has_image, has_video, has_gif)
    tags += collect_keyword_tags(full_text_concat)
    # original hashtags
    for t in thread:
        for h in t.get("entities", {}).get("hashtags", []):
            tag = h.get("text", "").lower()
            if tag:
                tags.append(f"hashtag-{tag}")
    tags = sorted(set(tags))

    # frontmatter
    fm_lines = ["---"]
    fm_lines.append(f'id: "{root_id}"')
    fm_lines.append(f"date: {created.strftime('%Y-%m-%dT%H:%M:%SZ')}")
    fm_lines.append(f"url: https://twitter.com/{USERNAME}/status/{root_id}")
    fm_lines.append(f"likes: {root_likes}")
    fm_lines.append(f"retweets: {root_rts}")
    if len(thread) > 1:
        fm_lines.append(f"thread: true")
        fm_lines.append(f"thread_length: {len(thread)}")
        fm_lines.append(f"thread_likes_total: {total_likes}")
        fm_lines.append(f"thread_retweets_total: {total_rts}")
    else:
        fm_lines.append(f"thread: false")
    if media_count:
        fm_lines.append(f"media: {media_count}")
    if all_mentions:
        fm_lines.append("mentions: [" + ", ".join(sorted(all_mentions)) + "]")
    if tags:
        fm_lines.append("tags:")
        for t in tags:
            fm_lines.append(f"  - {t}")
    fm_lines.append("---")

    # body
    body_lines = []
    for i, t in enumerate(thread, 1):
        if len(thread) > 1:
            body_lines.append(f"## {i}/{len(thread)}")
            body_lines.append("")
        text = render_tweet_body(t)
        if text:
            body_lines.append(text)
            body_lines.append("")
        # embed media
        for f in media_by_tweet.get(t["id_str"], []):
            target = ATTACH / f.name
            if not target.exists():
                shutil.copy2(f, target)
                media_copied += 1
            body_lines.append(f"![[{f.name}]]")
            body_lines.append("")
        # per-tweet stats inside thread
        if len(thread) > 1:
            likes = int(t.get("favorite_count", 0))
            rts = int(t.get("retweet_count", 0))
            body_lines.append(f"*❤ {likes} · 🔁 {rts}*")
            body_lines.append("")

    body_lines.append("---")
    body_lines.append("")
    if len(thread) > 1:
        body_lines.append(f"*Thread of {len(thread)} · {created.strftime('%Y-%m-%d %H:%M UTC')} · ❤ {total_likes} total · 🔁 {total_rts} total*  ")
    else:
        body_lines.append(f"*{created.strftime('%Y-%m-%d %H:%M UTC')} · ❤ {root_likes} · 🔁 {root_rts}*  ")
    body_lines.append(f"[View on Twitter →](https://twitter.com/{USERNAME}/status/{root_id})")
    body_lines.append("")

    fpath.write_text("\n".join(fm_lines) + "\n\n" + "\n".join(body_lines), encoding="utf-8")
    return 1, media_copied


if __name__ == "__main__":
    main()
