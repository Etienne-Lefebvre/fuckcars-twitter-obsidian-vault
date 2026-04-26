# FuckCarsReddit Twitter Archive to Obsidian Vault

I ran the [@FuckCarsReddit](https://twitter.com/FuckCarsReddit) Twitter account. I mainly posted urbanist memes and rants about cars, parking, transit, housing, and sprawl. This is the full archive of my original posts, dumped into an [Obsidian](https://obsidian.md) vault so people can actually find old stuff. Twitter's search is borderline useless, and I have no idea how long the platform will keep working.

## What's in here

- 1,180 notes, one per original tweet or self-thread (I dropped pure retweets and replies to other people)
- 1,647 images, videos, and GIFs from the posts, embedded in the notes
- Posts split into year folders: `posts/2021/`, `posts/2022/`, etc.
- Topical tags across 22 categories (parking, transit, housing, sprawl, climate, etc.)
- Structural tags like `viral` (≥1k likes), `mega-viral` (≥10k), `popular`, `thread`, `has-media`
- Original metadata: like and retweet counts, post date, link back to the source tweet

The archive runs from December 2021 (when I made the account) through April 2026.

## How to read the vault

### 1. Install Obsidian

Obsidian is a free app that reads plain Markdown files from a folder. Windows, Mac, Linux, iOS, Android. Grab it at [obsidian.md](https://obsidian.md). Run the installer, no account or signup.

### 2. Download this repo

You don't need a GitHub account or git knowledge:

1. Click the green `Code` button on the repo page.
2. Click "Download ZIP".
3. Unzip it somewhere. Your Documents folder is fine.

You'll end up with a folder called `fuckcars-twitter-obsidian-vault-main` or similar.

### 3. Open it as a vault

1. Launch Obsidian.
2. Click "Open folder as vault" (or use the vault switcher in the bottom-left if you already have a vault open).
3. Pick the folder you just unzipped.
4. If it asks, click "Trust author and enable plugins". There aren't any plugins in here, so it's harmless either way.

Done. Browse the `posts/` folder by year, or just search.

## What is Obsidian?

Obsidian is a free local-first app that turns a folder of Markdown files into a searchable knowledge base. People mostly use it for personal notes, but it works just as well for reading something like this archive.

A few things to know:

- All the files live on your computer. No cloud, no account, nothing on anyone else's server.
- It's free for personal use. They sell paid sync and publishing tiers, but you don't need either to read this.
- There's a Reading view and an Editing view, switched with `Ctrl+E` (or `Cmd+E` on Mac). Reading view actually shows the embedded images, which is what you want for browsing.

## How to search

### Basic search

`Ctrl+Shift+F` (or `Cmd+Shift+F`) opens vault-wide search. Some examples:

- `parking minimum` finds every post that mentions it
- `tag:#viral` shows only the viral ones
- `tag:#parking tag:#north-america` narrows to parking posts about NA cities

### Search with Dataview (optional)

If you install the [Dataview](https://blacksmithgu.github.io/obsidian-dataview/) community plugin (Settings → Community plugins → Browse → search "Dataview"), you can write SQL-style queries against the metadata. For example:

```dataview
TABLE likes, retweets
FROM "posts"
WHERE contains(tags, "parking") AND likes > 500
SORT likes DESC
```

```dataview
TABLE likes, length(file.outlinks) as media
FROM "posts"
WHERE contains(tags, "viral") AND contains(tags, "transit")
SORT likes DESC
LIMIT 20
```

## Folder structure

```
posts/
  2021/   - 9 notes
  2022/   - 327 notes
  2023/   - 641 notes
  2024/   - 189 notes
  2025/   - 14 notes
attachments/   - 1,647 image/video/GIF files
```

Each note starts with a YAML metadata block, then the actual post (text plus embedded media), then a footer with a link back to the original tweet.

## How I made this archive

Started from Twitter's official "request your archive" download. From there:

1. Filter the dump down to my own original posts and self-threads. Drop retweets and replies to other people.
2. Stitch multi-tweet threads back into single notes.
3. Apply structural tags (`viral`, `popular`, `thread`, `has-media`) based on engagement and media counts.
4. Send each post to Claude Haiku 4.5 to assign topical tags from a 22-category list I came up with.

The two Python scripts I used (`_convert.py` and `_llm_tag.py`) are in the repo if you want to see how it works. You don't need them to read the vault.

## A note on tag accuracy

The topical tags came from an LLM, so some are going to be off. I tested and tuned the classification prompt before running the full pass, but it's not perfect. If you find a note that's clearly mistagged, open an issue. The actual tweet text is always the source of truth. If a tag is misleading you, just search by keyword.

## License & attribution

These are my own posts. Read them, share them, reference them, go for it. If you cite something from the archive in your own writing, link to the original tweet (every note has a "View on Twitter" link at the bottom).
