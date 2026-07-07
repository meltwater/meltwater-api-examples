# CLAUDE.md — Reputation Watchdog

Instructions for you (Claude) when asked to run this directly — e.g. in Claude Code using a
connected Meltwater MCP connector, instead of running the standalone `reputation_watchdog.py`.
(Human setup: `RUNNING-IN-CLAUDE-CODE.md`. Full details: `README.md`.)

**Scope of the task:** when the user asks to "run the Reputation Watchdog" for a watch config,
produce the **fused alert** end to end: scan Meltwater → read the first-party source → fuse →
present the alert markdown. The point of the demo is the **fusion** — Meltwater's external signal
joined with the company's OWN data, an insight neither has alone.

## Load the watch config

Read the chosen `watches/*.json` (default `watches/example-watch.json`, or the one the user
names). It carries the saved-search id, first-party source,
regions, window/baseline, and an optional `asOf` date.

**The config (and any as-of the user types) is the SOLE source of truth for the scan date — work
out the date yourself, never copy it from anywhere else:**
- If `asOf` is a real date (e.g. `"2026-05-26"`), or the user gives one, anchor "today" to it.
- If `asOf` is absent, JSON `null`, or the string `"null"`/`""`/`"today"`, use **today's actual
  calendar date** (a real-time run). Do not substitute any other date.

Then derive the windows: the anomaly window is the trailing `windowHours` of the anchor day; the
baseline is the `baselineDays` before it. **Label the anchor date in the alert.**

⚠️ **Do NOT take the date (or the volumes, sources, sentiment) from `sample_output/brief.md`.**
That file is illustrative *output* from one past run (anchored to 26 May 2026) — use it only as a
guide to the alert's *shape/format*, never for its values. Pulling its `2026-05-26` date into a
real-time run is a bug.

## Step 1 — Meltwater scan (uses the connector)

Tools:
- `unified_retrieval_statistics_retrieval_tool` — daily volume (baseline vs anomaly window),
  sentiment breakdown, top sources.
- `unified_retrieval_document_retrieval_tool` (sortBy reach) — driving headlines in-window.
- a saved-search **list** tool (e.g. `list_searches_metadata`) — for the resolution step.
- `unified_retrieval_query_gen_tool` — fallback only (see below).

Always pass `query:"*"` with the saved-search id so results sort by metric, not semantic
similarity. **Search resolution:** list the account's searches, propose the best match for the
watch, then ground on the configured `savedSearch.id` (the authority). If that id is still a
placeholder, fall back to `query_gen` on the watch name and say so in the alert footer.

## Step 2 — First-party fusion

Prefer running `mock_firstparty/server.py` and calling
`get_support_signal(issue, as_of=<the anchor date>, days=10)` — it returns the signal for the
scanned day (elevated during the 26 May 2026 episode, baseline otherwise). If instead you read
`mock_firstparty/support_data.json` directly, **apply its `incident.active_window` yourself**: use
the `incident` figures only if the anchor date falls inside that window; otherwise use the
`baseline` figures. Do not present the May spike as a live signal on a date outside its window.

Either way, look for where external coverage and internal signal agree — especially by region. On
a normal day both are quiet: that's a clean all-clear, not something to force into alarm.

## Step 3 — Write the alert

Fuse both into the brief, following the *shape* of `sample_output/brief.md` (headings, tone,
length) — but with **this run's own** date and figures, never that sample's. **Set the status
honestly:** 🔴 HIGH / 🟠 MEDIUM for a real anomaly (spike vs baseline and/or sharp negative
sentiment, especially if the first-party signal corroborates); 🟢 ALL CLEAR on a quiet day
(normal volume, benign sentiment, no internal movement) — keep an all-clear short, and don't
manufacture alarm. Call out regions where both agree (or why the all-clear holds), and 1–2 next
steps. Never invent figures — use only what the tools return.

Use a **demo/sandbox** Meltwater account; **no real customer PII**.
