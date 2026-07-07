# Running it without writing code (Claude Code / MCP clients)

The fastest way to see this reference work is to let an **MCP client act as the agents** — no
Python, no API token. You connect the Meltwater MCP server, open this repo, and ask the client
to run it. It reads `CLAUDE.md`, plays the two agent roles in sequence, and renders the HTML.

This is a great first look. When you're ready to run it **headless / repeatably** (or wire the
insight sub-agent into your *own* orchestrator — the real point of the pattern), move to the
standalone `social_brief_subagent.py`; see `README.md`.

These steps use **Claude Code**; any MCP client that can connect the Meltwater MCP server and
read a local repo works similarly.

## 1. Connect Meltwater MCP

Connect the **Meltwater MCP** server in your client and complete auth. You only need this one
connector — it's scoped to your Meltwater account.

## 2. Configure your campaign

Copy `campaigns/example-campaign.json` and fill in:

- `brand` / `wordmark` — identity on the brief
- `market` / `interestArea` / `audience.label` / `objective` — the briefing request
- `savedSearch.id` — your Meltwater **landscape** saved-search id (the wider interest-area
  conversation, **not** your brand mentions)
- `theme` — optional colours

## 3. Open the repo and run it

Open this folder in Claude Code and say:

> **"Generate the social campaign brief for `campaigns/example-campaign.json`."**

(Say "generate the brief", not "run the sub-agent" — you want the *whole* flow through to the
HTML, not just the Meltwater insight half.)

It will run both agents end to end:
1. **As the Meltwater insight sub-agent:** resolve/propose the search (grounding on the
   configured id), pull the landscape (statistics + top documents, `query:"*"`), and synthesise
   the insight payload.
2. **As your own agent (no Meltwater access):** author the campaign brief from those
   insights.
3. Render the brief to a single HTML file.

Open the HTML and use **Save as PDF** to share it.

## Notes

- **Keep the boundary honest.** The whole point is that the brief is written from the insight
  payload, not from fresh Meltwater calls. Once you switch to Role 2, don't call the connector
  again.
- **It may make follow-up pulls** in Role 1 — a broad pull then a tighter one. That adaptive
  re-querying is the agent doing analytical work, not a bug.
- **Runs aren't perfectly identical** — the model chooses the sequence. For a deterministic,
  schedulable version, use the standalone script.
- **Design/template iteration needs no Meltwater at all:** `render.py` turns any brief JSON into
  HTML on its own — see the render-only command in `README.md`.
