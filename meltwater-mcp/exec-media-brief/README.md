# Exec Media Brief — a reference agent on Meltwater MCP

> **Draft reference implementation.** Shows how to build your *own* agent that uses **Meltwater
> MCP** to produce a finished, branded **executive daily media brief** — news + social,
> selected, ranked and rendered — and deliver it **headless, every morning, before anyone's
> awake**. Built by a customer's own team, running in their own infrastructure — not a chat in
> Claude.

An **accessible starting point** for building on Meltwater MCP: pure Meltwater, one credential,
a great-looking artifact on day one. (A natural next step — fusing Meltwater with your own
first-party data — is sketched under *What's next* below.)

## What it does

```
   COLLECT (Meltwater MCP)  ──▶  BRIEF (dict)  ──▶  RENDER (render.py)  ──▶  deliver
```

| Step | Meltwater MCP tool | What it gets |
|---|---|---|
| Volume vs norm | `unified_retrieval_statistics_retrieval_tool` (count by day) | Today's volume vs the 30-day baseline → the "hot day" signal |
| Sentiment | `unified_retrieval_statistics_retrieval_tool` (sentiment breakdown) | pos/neu/neg overall and per platform |
| Top sources | `unified_retrieval_statistics_retrieval_tool` (top sources) | Who's driving coverage |
| Headlines | `unified_retrieval_document_retrieval_tool` (sortBy reach) | Earned-media lead + stories |
| Earned social | `unified_retrieval_document_retrieval_tool` (sortBy views) | UGC ranked by views, with per-platform floors |
| Competitors | competitor saved search | Competitor news + social share-of-voice |

The model reasons over the results, applies the editorial rules, and emits one **structured
`BRIEF`**. `render.py` turns that into a single flat HTML file — exec-ready, prints straight to
PDF, works in any browser or email client. No bundler, no external fonts, no client-side JS.

## Why build an agent for this?

The value is **headless orchestration + delivery**: it runs on a schedule in *your* infra,
assembles the brief, and pushes it to *your* channel — no human in a chat. That "runs itself and
lands in the inbox every morning" loop is what makes it worth building as an agent rather than
doing by hand.

## Ways to run it

- **In Claude Code (no code) — quickest:** let Claude Code act as the agent using your connected
  Meltwater MCP connector. See `RUNNING-IN-CLAUDE-CODE.md`. Great for a first look.
- **Standalone (this repo):** `exec_media_brief.py` runs entirely in your own process — the
  schedulable, production path. Meltwater auth is a **single seam** (`MELTWATER_API_TOKEN`, sent
  as a bearer token) — fill it in and it runs end-to-end.
- **Later — OAuth:** when Meltwater's per-user OAuth clients are available, swap the static token
  for an OAuth credential. Same code, different credential.

## Credentials

You need two things:

1. **An Anthropic API key** — the agent's reasoning. Create one at
   [console.anthropic.com](https://console.anthropic.com) → **Settings → API Keys**, then:
   ```bash
   export ANTHROPIC_API_KEY="sk-ant-…"
   ```
2. **A Meltwater MCP API token** — access to your Meltwater data (from your Meltwater account team):
   ```bash
   export MELTWATER_API_TOKEN="…"
   ```

Either `export` them (as above) or put them in a `.env` file (`cp .env.example .env` and fill it
in) — the script loads `.env` automatically, and exported vars take precedence. The code never
hardcodes a key, so nothing leaks when you share it.

## Quickstart (standalone)

```bash
uv sync                                   # installs deps (anthropic[mcp], python-dotenv, mcp)
cp .env.example .env                      # add ANTHROPIC_API_KEY and MELTWATER_API_TOKEN
uv run python exec_media_brief.py --out brief.html
open brief.html                           # then "Save as PDF" from the report
```

**Render only** (no Meltwater needed — useful for template/design work):

```bash
uv run python render.py sample_output/sample_brief.json --out sample_output/brief.html
```

See `sample_output/brief.html` for what a finished brief looks like (fictional demo brand).

## Make it your brand

Everything brand-specific lives in **one JSON file** — fork `brands/example-brand.json`:

- `name` / `wordmark` / `logoUrl` — masthead identity
- `savedSearches.brand` / `.competitors` — your Meltwater saved-search IDs (the authority on
  relevance; the agent queries them with `query:"*"` — see below)
- `competitors` — the watchlist for the competitor section
- `floors` — per-platform inclusion thresholds (views for social, reach for the rest)
- `theme` — colours + fonts (see below)

Point `BRAND_CONFIG` at your copy (or pass `--brand path/to/brand.json`).

### Theme colours

Every `theme` key is optional — omit one and the template's neutral default is used. Each maps
to a CSS variable that `render.py` injects, so you can restyle the whole brief from the config
without touching the template. What each one paints:

| Key | Paints |
|---|---|
| `primary` | The brand accent. Section pills (`01 Earned Media`), story kickers, headline hover, links, the Reddit engagement number, quote-bar accents, the footer brand name, and the "Save as PDF" button. This is the one colour most brands need to set. |
| `primaryHi` | Darker shade of `primary` for hover/pressed states (e.g. the PDF button on hover). Set it a few steps darker than `primary`. |
| `ink` | The dark surfaces: the two masthead "glance" boxes (volume + sentiment), the "Daily Brief" title, the dark **Bottom line** panel, and card headings. |
| `accentWarm` | The small tag pill inside the Bottom line header ("at a glance"). Minor accent. |
| `surface` | The report "paper" — the page the brief sits on. |
| `page` | The area *behind* the report (the desk it rests on). |
| `card` | Card and tile backgrounds (stories, sentiment tiles). |
| `cardAlt` | Soft fills: the Executive Summary panel, hero pull-quote boxes, and social metric chips. |

Fonts: `fontDisplay` (headlines / big numbers) and `fontBody` (everything else) take any CSS
`font-family` value. Defaults are the system UI stack — self-contained, no web-font fetch. Point
them at a hosted web font only if you're willing to add the `@font-face` rules yourself.

Sentiment colours (positive green / negative red / neutral grey) are **fixed** — they carry
meaning, so they're intentionally not themeable.

### The one query trick worth knowing

Always pass `query:"*"` **with** a saved-search id. The saved search is the sole authority on
relevance; adding a descriptive query string triggers a semantic re-rank that *suppresses*
high-reach / high-view posts. `query:"*"` disables the re-rank so results sort purely by the
metric you asked for (views / reach). This is baked into the agent's instructions.

## What's next (documented, not built)

- **First-party fusion:** overlay your own owned-content calendar, campaign timeline or CRM so
  the brief says *"heavy negative on X — note our post on X ships at 2pm, consider holding."* The
  insight neither source produces alone. This repo is deliberately single-source to stay simple;
  fusion is the natural upgrade.
- **Owned social:** out of scope here — it needs you to connect your own social accounts. This
  agent covers earned news + social only.

## Adapt it to your use case

1. Fork the brand config; point the saved searches at your brand.
2. Schedule `exec_media_brief.py` (cron / Lambda / Cloud Run) for a daily headless run.
3. Add a delivery step after the render — post to Slack, email it, or drop it on a file host.
   (The agent ships without one; the deliverable is the HTML file.)

---
*Example data in `sample_output/` is a fictional brand ("Northwind Coffee") with invented
figures. Live runs pull real data from your own Meltwater saved searches.*
