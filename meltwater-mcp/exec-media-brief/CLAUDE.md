# CLAUDE.md — Exec Media Brief

Instructions for you (Claude) when asked to produce the brief directly — e.g. in Claude Code using
a connected Meltwater MCP connector, instead of running the standalone `exec_media_brief.py`.
(Human setup steps: `RUNNING-IN-CLAUDE-CODE.md`. Full spec: `README.md`.)

## Tools

Use the Meltwater connector's retrieval tools directly — you don't need to check the account or
select a connector:

- `unified_retrieval_statistics_retrieval_tool` — aggregate metrics (volume, sentiment, top sources)
- `unified_retrieval_document_retrieval_tool` — the posts / articles themselves
- `unified_retrieval_query_gen_tool` — only if a saved-search ID is missing (normally not needed)

Always pass `query:"*"` alongside a saved-search ID so results sort by the requested metric, not by
semantic similarity (a descriptive query string suppresses high-reach/high-view posts).

## When asked to "run the exec media brief"

Default brand `brands/example-brand.json`, or the brand the user names.

1. **Load the brand config** — read the chosen `brands/*.json` for the saved-search IDs,
   competitor watchlist, platform floors, and theme.
2. **Collect** with the tools above (brand's saved searches, always `query:"*"`):
   - **statistics_retrieval_tool** — daily volume vs the ~30-day norm; then sentiment breakdown
     (overall + per platform); then top sources.
   - **document_retrieval_tool** (sortBy reach) — earned-media headlines.
   - **document_retrieval_tool** (sortBy views) — earned/UGC social; apply the brand's
     per-platform floors (views for Twitter/Instagram/TikTok, reach otherwise).
   - **document_retrieval_tool** + the competitor saved-search ID — competitor news + social.
3. **Assemble the `BRIEF`** per the schema and editorial rules in `scan_instruction.md` (and the
   shape of `sample_output/sample_brief.json`): 3-sentence exec summary, highest-reach earned
   story as the hero, brand's own voices first in quotes, never invent figures — use only what
   Meltwater returns.
4. **Render** with `render.py`:
   `python render.py <brief.json> --brand <brand.json> --out brief.html`
   (write the BRIEF to a temp json, or call `render.render_to_file(brief, brand, out)`).
5. **Present** the HTML brief. It prints straight to PDF from the report's button.
