# CLAUDE.md — Social Brief Sub-Agent

Instructions for you (Claude) when asked to run this directly — e.g. in Claude Code using a
connected Meltwater MCP connector, instead of running the standalone
`social_brief_subagent.py`. (Human setup: `RUNNING-IN-CLAUDE-CODE.md`. Full details: `README.md`.)

**Scope of the task:** when the user asks to "generate the social campaign brief", "plan a social
campaign", or "run this" for a campaign config, they mean the **whole flow through to the HTML
brief** — not just the Meltwater insight half. ("Sub-agent" names the *pattern* Meltwater plays,
not the deliverable.) Always carry through: Role 1 → Role 2 → render → present the HTML.

This reference has **two agent roles**. When running it here, play them in sequence and keep the
boundary honest — the point is that Meltwater supplies *insight* and the host agent (yours) does
the *brief*.

## Role 1 — Meltwater Insight Sub-Agent (uses the connector)

Use the Meltwater connector's retrieval tools directly:
- `unified_retrieval_statistics_retrieval_tool` — volume trend, sentiment, top sources/themes
- `unified_retrieval_document_retrieval_tool` — the posts/articles (sortBy reach or views)
- a saved-search **list** tool (e.g. `list_searches_metadata`) — for the resolution step only

Always pass `query:"*"` alongside the saved-search id so results sort by the requested metric,
not by semantic similarity.

Follow `insight_instruction.md`. In short:
1. **Resolve (demonstrate, don't decide):** list the account's searches, propose the best match
   for the campaign's market + interest, then **ground on the configured `savedSearch.id`** from
   the campaign config regardless — it is the authority.
2. **Collect** (all `query:"*"` on that id): shape & mood (statistics), driving stories
   (documents, sortBy reach), driving social (documents, sortBy views).
3. **Synthesise** the INSIGHT PAYLOAD JSON — trends, cultural moments, notable voices,
   sentiment, and `whitespaceForBrand` (apply the brand as a lens; never invent data).

Output the insight payload as JSON. **Do not** write campaign concepts, copy, hashtags, channels
or timing — that's Role 2.

## Role 2 — Host Orchestrator, i.e. your own agent (NO connector access)

Now switch hats. You are the brand's own strategist and you have **only** the insight payload —
do not call Meltwater again. Follow `brief_instruction.md`: turn the insights into the CAMPAIGN
BRIEF JSON (2–3 concepts, formats, hashtags, channel plan, timing, watch-outs). Ground every
concept in a named insight; copy `sources` from the payload's `evidenceAppendix`; invent no
figures.

## Then render

`python render.py <brief.json> --campaign <campaign.json> --out brief.html`
(write the brief to a temp json, or call `render.render_to_file(brief, cfg, out)`), then present
the HTML. It prints to PDF from the report's button.

Default campaign config: `campaigns/example-campaign.json`, or the one the user names.
