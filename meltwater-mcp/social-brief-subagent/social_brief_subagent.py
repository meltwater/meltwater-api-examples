"""Social Brief Sub-Agent — reference for the *pull* sub-agent pattern on Meltwater MCP.

You already have your OWN agent. Meltwater is a specialist INSIGHT SUB-AGENT it delegates to.
This script shows both sides of that boundary end to end:

    MARKETER REQUEST
        -> YOUR ORCHESTRATOR (mock host agent — no Meltwater access)
        -> MELTWATER INSIGHT SUB-AGENT (Claude + Meltwater MCP tools)  ->  INSIGHT PAYLOAD
        -> YOUR ORCHESTRATOR authors the CAMPAIGN BRIEF from the insights
        -> RENDER (render.py)  ->  brief.html

The reusable asset is the CONTRACT between the two agents (the request in, the insight payload
out) — not the demo brand. Meltwater supplies the *insight*; your agent does the *creative*.
That division is enforced by architecture: the orchestrator is handed only the insight payload
— it never sees a Meltwater tool.

Why raw MCP tools (not a hosted skill): today the "Meltwater sub-agent" is Claude + the raw
retrieval tools + an analyst prompt. That is exactly the seam where a future Meltwater-hosted
`get_social_brief` skill would slot in — same contract, less code to own. See README.md.

Draft reference code — confirm SDK calls against installed versions before external use.
"""

import argparse
import asyncio
import json
import os
import sys
from contextlib import AsyncExitStack
from pathlib import Path
from string import Template

import anthropic
from anthropic.lib.tools.mcp import async_mcp_tool
from dotenv import load_dotenv
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

import render

# Load a local .env if present. Does NOT override variables already exported in the shell.
load_dotenv()

MODEL = "claude-opus-4-8"


def log(msg: str = ""):
    """Progress line to stderr, flushed so it appears live during a run/demo."""
    print(msg, file=sys.stderr, flush=True)


def _summarise_input(inp) -> str:
    """One-line summary of a tool call's arguments — enough to narrate what it's pulling."""
    if not isinstance(inp, dict):
        return ""
    interesting = ("query", "savedSearchIds", "saved_search_ids", "savedSearchId", "sortBy",
                   "sort_by", "metric", "statisticType", "statistic_type", "limit", "days")
    parts = [f"{k}={inp[k]}" for k in interesting if inp.get(k) not in (None, "", [])]
    summary = ", ".join(parts) if parts else ", ".join(list(inp.keys())[:4])
    return f"({summary[:90]})"


# --- AUTH SEAM -------------------------------------------------------------
# Meltwater auth is a single seam: set MELTWATER_API_TOKEN and the agent runs end-to-end. When
# per-user OAuth clients are available, swap the static token for an OAuth credential — same code.
MELTWATER_MCP_URL = os.environ.get("MELTWATER_MCP_URL", "https://api.meltwater.com/v2/mcp")
MELTWATER_API_TOKEN = os.environ.get("MELTWATER_API_TOKEN")
# ---------------------------------------------------------------------------

# The connector exposes many tools; the insight sub-agent needs only retrieval + a saved-search
# LIST tool (for the Step-1 resolution demo). Attach just these so the run is deterministic and
# context stays lean. List-tool names vary by connector, so we include the common candidates and
# attach whichever match; run() falls back to all tools (loudly) if none do.
INSIGHT_TOOLS = {
    "unified_retrieval_statistics_retrieval_tool",  # volume / sentiment / top sources
    "unified_retrieval_document_retrieval_tool",    # the posts / articles themselves
    "unified_retrieval_query_gen_tool",             # plain-English -> boolean (rarely needed)
    # saved-search list tools — for search resolution (Step 1). Names differ per connector:
    "list_searches_metadata",
    "listening_list_searches",
    "explore_plus_list_searches",
}

INSIGHT_INSTRUCTION_PATH = Path(__file__).with_name("insight_instruction.md")
BRIEF_INSTRUCTION_PATH = Path(__file__).with_name("brief_instruction.md")


def build_insight_instruction(cfg: dict) -> str:
    ss = cfg.get("savedSearch", {})
    values = {
        "brand": cfg.get("brand"),
        "market": cfg.get("market"),
        "interest_area": cfg.get("interestArea"),
        "audience_label": cfg.get("audience", {}).get("label"),
        "objective": cfg.get("objective"),
        "timeframe": cfg.get("timeframe", "last 30 days"),
        "search_id": ss.get("id"),
        "search_name": ss.get("name"),
    }
    return Template(INSIGHT_INSTRUCTION_PATH.read_text(encoding="utf-8")).substitute(values)


def build_brief_instruction(cfg: dict, insight_payload: dict) -> str:
    values = {
        "brand": cfg.get("brand"),
        "market": cfg.get("market"),
        "interest_area": cfg.get("interestArea"),
        "audience_label": cfg.get("audience", {}).get("label"),
        "objective": cfg.get("objective"),
        "timeframe": cfg.get("timeframe", "last 30 days"),
        "confidential": cfg.get("distribution", {}).get("confidential", ""),
        "insight_payload": json.dumps(insight_payload, indent=2, ensure_ascii=False),
    }
    return Template(BRIEF_INSTRUCTION_PATH.read_text(encoding="utf-8")).substitute(values)


def require_anthropic_credentials():
    """Fail early, clearly, if no Anthropic API key is set. The Python SDK reads
    ANTHROPIC_API_KEY / ANTHROPIC_AUTH_TOKEN — NOT the Claude Code / `ant` CLI OAuth login."""
    if os.getenv("ANTHROPIC_API_KEY") or os.getenv("ANTHROPIC_AUTH_TOKEN"):
        return
    sys.exit(
        "No Anthropic API key found. Get one at https://console.anthropic.com "
        "(Settings -> API Keys), then run:\n"
        '  export ANTHROPIC_API_KEY="sk-ant-..."'
    )


async def open_session(stack, url, headers=None):
    """Open an in-process MCP client session to `url`. Tools execute client-side."""
    read, write, _ = await stack.enter_async_context(
        streamablehttp_client(url, headers=headers or {})
    )
    session = await stack.enter_async_context(ClientSession(read, write))
    await session.initialize()
    return session


def parse_json(text: str) -> dict:
    """Extract a JSON object from a model message (tolerates fences/prose)."""
    t = text.strip()
    if t.startswith("```"):
        t = t.split("```", 2)[1].lstrip("json").strip() if "```" in t[3:] else t
    start, end = t.find("{"), t.rfind("}")
    if start == -1 or end == -1:
        raise ValueError(f"No JSON object found in model output:\n{text[:500]}")
    return json.loads(t[start:end + 1])


async def run_insight_subagent(client, cfg: dict) -> dict:
    """THE MELTWATER SIDE. Claude + Meltwater MCP tools grounds on the saved search and returns
    the INSIGHT PAYLOAD. This is the piece a hosted skill would one day replace."""
    async with AsyncExitStack() as stack:
        log("▸ [Meltwater sub-agent] Connecting to Meltwater MCP…")
        meltwater = await open_session(
            stack, MELTWATER_MCP_URL,
            headers={"Authorization": f"Bearer {MELTWATER_API_TOKEN}"},
        )
        listed = await meltwater.list_tools()
        selected = [t for t in listed.tools if t.name in INSIGHT_TOOLS]
        if not selected:
            available = ", ".join(t.name for t in listed.tools[:12])
            log(f"  WARN: none of INSIGHT_TOOLS matched the connector. Attaching all "
                f"{len(listed.tools)} tools. Available: {available}...")
            selected = listed.tools
        log(f"▸ [Meltwater sub-agent] Tools ready: {', '.join(t.name for t in selected)}")
        tools = [async_mcp_tool(t, meltwater) for t in selected]

        runner = client.beta.messages.tool_runner(
            model=MODEL,
            max_tokens=16000,
            thinking={"type": "adaptive"},
            messages=[{"role": "user", "content": build_insight_instruction(cfg)}],
            tools=tools,
        )
        log("▸ [Meltwater sub-agent] Resolving search, grounding, synthesising insight…")
        final, calls = None, 0
        async for message in runner:
            final = message
            tool_uses = [b for b in message.content if getattr(b, "type", None) == "tool_use"]
            for b in tool_uses:
                calls += 1
                log(f"   {calls:>2}. {b.name}  {_summarise_input(b.input)}")
            if not tool_uses and any(getattr(b, "type", None) == "thinking" for b in message.content):
                log("      · thinking…")
        log(f"▸ [Meltwater sub-agent] Done — {calls} Meltwater call(s). Insight payload ready.")

    text = "".join(b.text for b in final.content if getattr(b, "type", None) == "text")
    return parse_json(text)


async def run_host_orchestrator(client, cfg: dict, insight_payload: dict) -> dict:
    """YOUR SIDE. Your own agent (the host orchestrator) — deliberately given NO Meltwater tools.
    It receives only the insight payload and does the creative work: authors the CAMPAIGN BRIEF."""
    log("▸ [Your agent] Authoring the campaign brief from the insights (no Meltwater access)…")
    msg = await client.messages.create(
        model=MODEL,
        max_tokens=8000,
        messages=[{"role": "user", "content": build_brief_instruction(cfg, insight_payload)}],
    )
    text = "".join(b.text for b in msg.content if getattr(b, "type", None) == "text")
    return parse_json(text)


async def run(campaign_path: str, out_path: str):
    require_anthropic_credentials()
    if not MELTWATER_API_TOKEN:
        raise SystemExit(
            "MELTWATER_API_TOKEN not set. Add your Meltwater MCP API token to .env "
            'or export it:\n  export MELTWATER_API_TOKEN="…"'
        )
    cfg = json.loads(Path(campaign_path).read_text())
    log(f"\n▸ Social Brief Sub-Agent — {cfg.get('brand')} · {cfg.get('interestArea')} · "
        f"{cfg.get('market')}  ({Path(campaign_path).name})")

    client = anthropic.AsyncAnthropic()  # reads ANTHROPIC_API_KEY from env; never hardcode a key

    # 1) Meltwater sub-agent -> insight payload
    insight = await run_insight_subagent(client, cfg)

    # 2) Your orchestrator -> campaign brief (from insights only)
    brief = await run_host_orchestrator(client, cfg, insight)

    # Write the contract artefacts next to the HTML so the boundary is inspectable without a run.
    stem = Path(out_path).with_suffix("")
    Path(f"{stem}.insight.json").write_text(json.dumps(insight, indent=2, ensure_ascii=False))
    Path(f"{stem}.brief.json").write_text(json.dumps(brief, indent=2, ensure_ascii=False))
    log(f"▸ Contract artefacts: {stem}.insight.json (Meltwater) · {stem}.brief.json (your agent)")

    # 3) Render the brief the marketer sees
    n = len(brief.get("concepts") or [])
    log(f"▸ Brief assembled: '{brief.get('conceptName')}', {n} concept(s). Rendering…")
    render.render_to_file(brief, cfg, out_path)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Generate a social campaign brief via a Meltwater insight sub-agent.")
    ap.add_argument("--campaign", default=os.environ.get("CAMPAIGN_CONFIG", "campaigns/example-campaign.json"))
    ap.add_argument("--out", default="brief.html")
    args = ap.parse_args()
    asyncio.run(run(args.campaign, args.out))
