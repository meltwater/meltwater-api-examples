# Meltwater API Examples

### Build your own AI agents on Meltwater's media intelligence.

Runnable, forkable **reference agents** that call the **Meltwater MCP** server to do real PR &
comms work — crisis monitoring, executive briefings, campaign insight — as code that runs in
*your* systems. Not a chatbot and not a dashboard: agents your team owns, schedules, and wires
into its own data.

Each example is a complete starting point — **one config file to make it yours, one credential
to run it, a polished result on day one.** Fork one and you can have a working proof-of-concept
this afternoon.

---

## What you can build

### 🗞️ Exec Media Brief — [`meltwater-mcp/exec-media-brief`](meltwater-mcp/exec-media-brief)
A branded, executive-ready media brief — news + social, selected, ranked and rendered to a
self-contained HTML page — delivered **headless every morning, before anyone's awake.** Pure
Meltwater, one credential, a great-looking artifact on day one.

### 🚨 Reputation Watchdog — [`meltwater-mcp/reputation-watchdog`](meltwater-mcp/reputation-watchdog)
Scans a brand's coverage for an anomaly against its 30-day norm, then **fuses it with your own
first-party data** (support desk, CRM, claims) into an alert neither source could give alone —
*"the same regions were lighting up in our own data days before the story broke."* Shows how to
join Meltwater with a **private** internal system, inside your own agent.

### 🧭 Social Brief Sub-Agent — [`meltwater-mcp/social-brief-subagent`](meltwater-mcp/social-brief-subagent)
Already building your own agent platform? Plug Meltwater in as a **specialist insight sub-agent**:
your orchestrator asks for a grounded landscape read on a brand × market × topic, and Meltwater
returns the trending stories, cultural moments and whitespace — your agent writes the campaign
brief. Meltwater as a source of insight inside *your* agentic stack.

---

## Try one in ~5 minutes

```bash
cd meltwater-mcp/exec-media-brief
uv sync                       # installs deps
cp .env.example .env          # add your Anthropic API key + Meltwater MCP token
uv run python exec_media_brief.py --out brief.html
open brief.html               # a finished, branded brief — prints straight to PDF
```

Every example follows the same shape and ships with its own README, a fictional demo config you
can run as-is, and a **no-code path** (below). Prefer to look before you install? Each folder's
`sample_output/` shows a finished result.

## You need two credentials

- **An Anthropic API key** — the agent's reasoning ([console.anthropic.com](https://console.anthropic.com) → API Keys).
- **A Meltwater MCP API token** — access to your Meltwater data (from your Meltwater account team).

Drop them in `.env` and go — nothing is hardcoded, so nothing leaks when you share your fork.

## Three ways to run every example

- **No code (fastest look)** — let an MCP client like **Claude Code** act as the agent via your
  connected Meltwater connector. See each example's `RUNNING-IN-CLAUDE-CODE.md`.
- **Standalone Python** — the production-shaped path; runs entirely in your own process, one
  Meltwater credential as the only external seam.
- **Headless / scheduled** — drop it on cron / Lambda / Cloud Run so it *runs itself* and lands
  in your channel. That self-running loop is the reason to build an agent rather than do it by hand.

## Why an agent, not the app?

The value is the **orchestration you own**: it runs on your schedule, in your infrastructure,
joined with your own data, delivered to your channel — no human in a chat. These examples teach
that pattern on real PR & comms workflows, as code you can fork and ship.

## What is Meltwater MCP?

The [Model Context Protocol](https://modelcontextprotocol.io) is an open standard for giving AI
agents tools. **Meltwater MCP** exposes Meltwater's news & social intelligence as MCP tools, so
your agent can query coverage, sentiment, sources and posts directly. For the full API reference,
tool catalogue and quickstart, see the **Meltwater Developer Portal** at
[developer.meltwater.com](https://developer.meltwater.com) — this repository provides the runnable
examples that complement it.

## Repository structure

Examples are grouped by the Meltwater product they use, then by use case:

```text
meltwater-mcp/
  exec-media-brief/         # scheduled, branded daily media brief (HTML)
  reputation-watchdog/      # anomaly detection fused with your own first-party data
  social-brief-subagent/    # Meltwater as an insight sub-agent to your orchestrator
```

---

*Draft reference implementations — starting points to fork, not turnkey products. Confirm SDK
calls against your installed versions before production use.*
