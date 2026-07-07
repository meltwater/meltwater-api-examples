# Running it without writing code (Claude Code / MCP clients)

The fastest way to see this agent work is to let an **MCP client act as the agent** — no Python,
no API token. You connect the Meltwater MCP server, open this repo, and ask the client to run the
scan. It reads `CLAUDE.md`, calls the Meltwater tools, reads the bundled first-party source,
fuses both, and produces the alert.

When you're ready to run it **headless on a schedule** (the point of a watchdog), move to the
standalone `reputation_watchdog.py` — see `README.md`.

These steps use **Claude Code**; any MCP client that can connect the Meltwater MCP server and read
a local repo works similarly.

## 1. Connect Meltwater MCP

Connect the **Meltwater MCP** server in your client and complete auth. You only need this one
connector — it's scoped to your Meltwater account.

## 2. Configure your watch

Copy `watches/example-watch.json` and fill in:

- `name` / `brand` — the subject of the scan
- `savedSearch.id` — your Meltwater saved-search id for the brand/topic (the relevance authority)
- `firstParty` — your internal source (the bundled mock stands in for it)
- `regions` — where to look for external/internal agreement
- `windowHours` / `baselineDays` — the anomaly window and baseline
- `asOf` — leave `null` for real-time, or set a date to anchor the scan (backfill / demo)

## 3. Open the repo and run it

Open this folder in Claude Code and say:

> **"Run the Reputation Watchdog for `watches/example-watch.json`."**
> *(or anchor it to a past day: "…for `watches/example-watch.json`, as of 26 May 2026.")*

It will:
1. Resolve/propose the saved search (grounding on the configured id), compare the anomaly window
   to the ~30-day norm, pull sentiment, top sources and driving headlines.
2. Read the first-party source for the same issue/regions.
3. Fuse both into the alert — calling out where external and internal agree.

## Notes

- **The spike depends on the day.** On a quiet day there's nothing anomalous to show. For a demo,
  set an `asOf` date on a day with a known event (e.g. the Toyota example, 26 May 2026). The data
  is real; you're just anchoring "today", and the alert says so.
- **Keep the fusion honest** — the alert should draw on both the Meltwater scan *and* the
  first-party signal; that join is the whole point.
- **Runs aren't perfectly identical** — the model chooses the sequence. For a deterministic,
  schedulable version, use the standalone script.
- Use a **demo/sandbox** Meltwater account; **no real customer PII**.
