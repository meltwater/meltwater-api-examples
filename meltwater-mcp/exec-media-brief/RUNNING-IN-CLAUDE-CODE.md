# Running it without writing code (Claude Code / MCP clients)

The fastest way to see this agent work is to let an **MCP client act as the agent** — no Python,
no API token. You connect the Meltwater MCP server, open this repo, and ask the client to run the
brief. It reads the instructions in `CLAUDE.md`, calls the Meltwater tools, assembles the brief,
and renders the HTML for you.

This is a great first look. When you're ready to run it **headless on a schedule** (the point of a
custom agent), move to the standalone `exec_media_brief.py` — see `README.md`.

These steps use **Claude Code**; any MCP client that can connect the Meltwater MCP server and read
a local repo works similarly.

## 1. Connect Meltwater MCP

Connect the **Meltwater MCP** server in your client. In Claude Code, add it as an MCP server
(`claude mcp add …`) or enable it as a connector, and complete auth. You only need this one
connector — it's scoped to your Meltwater account, so the agent doesn't need to pick between
accounts or look anything up.

## 2. Configure your brand

Copy `brands/example-brand.json` and fill in:

- `name` / `wordmark` — masthead identity
- `savedSearches.brand` and `savedSearches.competitors` — your Meltwater **saved-search IDs**
  (create these in Meltwater first; they define what "your coverage" and "competitors" mean)
- `competitors` — the watchlist for the competitor section
- `floors` — per-platform inclusion thresholds
- `theme` — optional colours/fonts (see "Theme colours" in `README.md`)

## 3. Open the repo and run it

Open this folder in Claude Code and say:

> **"Run the exec media brief for `<your-brand-config>`."**

It will:
1. Read your brand config.
2. Pull volume-vs-30-day-norm, sentiment, top sources, headlines, earned/UGC social and
   competitors from Meltwater (via the retrieval tools).
3. Assemble the structured brief and render it to a single HTML file.

Open the HTML and use the **Save as PDF** button in the report to share it.

## Notes

- **It may make follow-up pulls.** The agent reasons over what it gets back — e.g. a first broad
  pull, then a tighter one to surface posts that clear your view floors. That adaptive re-querying
  is expected and is the agent doing editorial work, not a bug.
- **Runs aren't perfectly identical.** Because the model chooses the sequence, two runs on the
  same day may differ slightly. For a deterministic, schedulable version, use the standalone
  script.
- **Design/template iteration needs no Meltwater at all:** `render.py` turns any BRIEF JSON into
  HTML on its own — see the render-only command in `README.md`.
