# Workflow: Twitter archive → Obsidian vault

```mermaid
flowchart TD
    A([Start: Twitter archive zip<br/>4,428 tweets]) --> B[Unzip + inspect data/*.js files]
    B --> C[Plan: 1 note per tweet/thread<br/>+ YAML frontmatter + tags]

    C --> P1[<b>Phase 1: Convert</b><br/>local, free]
    P1 --> D1[Write _convert.py]
    D1 --> D2[Filter retweets + replies-to-others<br/>4,428 → 1,831 tweets]
    D2 --> D3[Stitch self-threads<br/>1,831 → 1,180 notes]
    D3 --> D4[Apply structural tags<br/>viral, has-media, thread, image]
    D4 --> D5[Apply keyword tags<br/>regex on urbanist topics]
    D5 --> D6[Copy 1,647 media files<br/>to attachments/]
    D6 --> D7([Vault: 1,180 .md notes])

    D7 --> E[Move vault to<br/>OneDrive/Obsidian Vaults/]

    E --> P2[<b>Phase 2: LLM tagging</b><br/>Anthropic API]
    P2 --> F3[pip install anthropic<br/>+ set ANTHROPIC_API_KEY]
    F3 --> F4[Write _llm_tag.py<br/>Haiku 4.5 + prompt caching<br/>+ tool use + 22-tag taxonomy]
    F4 --> F5[Test on 5 notes]
    F5 --> F6{Tags accurate?}
    F6 -->|data-chart over-applied| F7[Tighten SYSTEM_PROMPT] --> F5
    F6 -->|looks good| F8[Run full pass<br/>~$1.90 · ~30 min · resumable]
    F8 --> G([End: searchable vault<br/>structural + topical tags<br/>queryable via Dataview])

    style A fill:#FFE4B5,color:#000
    style G fill:#90EE90,color:#000
    style D7 fill:#cce5ff,color:#000
    style F8 fill:#FFE4B5,stroke:#FF8C00,stroke-width:3px,color:#000
    style P1 fill:#f0f0f0,color:#000
    style P2 fill:#f0f0f0,color:#000
```

## Where you are now

The orange-outlined node (**Run full pass**) is your current step. Test runs are
done, prompt is tightened, you're ready to kick off the full ~30-minute LLM pass.

## Two-phase summary

**Phase 1 (done):** Local Python conversion — `_convert.py` filtered the archive,
stitched threads, applied regex-based topical tags, and copied media. Output:
1,180 notes ready to use in Obsidian.

**Phase 2 (in progress):** LLM tagging — `_llm_tag.py` sends each note to Claude
Haiku 4.5 to upgrade the keyword-based tags to a curated 22-tag taxonomy.
Structural tags from Phase 1 (viral, has-media, etc.) are preserved.

## Files involved

| File | Purpose |
|---|---|
| `_convert.py` | Phase 1 conversion script |
| `_llm_tag.py` | Phase 2 LLM tagging script |
| `posts/YYYY/*.md` | The notes themselves, organized by year |
| `attachments/*` | Media files (images, videos, GIFs) |
