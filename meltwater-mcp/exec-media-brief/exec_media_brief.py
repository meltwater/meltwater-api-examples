"""Exec Media Brief — standalone reference agent on Meltwater MCP.

Collects news + social from Meltwater, assembles a structured BRIEF, and renders a
branded HTML brief:

    COLLECT (Meltwater MCP)  ->  BRIEF (dict)  ->  RENDER (render.py)  ->  deliver

What it is, why it's a custom agent, the auth stages, and how to fork it for a brand:
see README.md.

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

# Load a local .env if present. Does NOT override variables already exported in the shell, so
# `export ANTHROPIC_API_KEY=…` still wins. Must run before the env constants below are read.
load_dotenv()

MODEL = "claude-opus-4-8"


def log(msg: str = ""):
    """Progress line to stderr, flushed so it appears live during a run/demo. On stderr so it
    never mixes into stdout if you pipe the output somewhere."""
    print(msg, file=sys.stderr, flush=True)


def _summarise_input(inp) -> str:
    """One-line summary of a tool call's arguments — enough to narrate what it's pulling."""
    if not isinstance(inp, dict):
        return ""
    interesting = ("query", "savedSearchIds", "saved_search_ids", "sortBy", "sort_by",
                   "metric", "statisticType", "statistic_type", "platform", "limit", "days")
    parts = [f"{k}={inp[k]}" for k in interesting if inp.get(k) not in (None, "", [])]
    summary = ", ".join(parts) if parts else ", ".join(list(inp.keys())[:4])
    return f"({summary[:90]})"

# --- AUTH SEAM -------------------------------------------------------------
# Meltwater auth is a single seam: set MELTWATER_API_TOKEN and the agent runs end-to-end. When
# per-user OAuth clients are available, swap the static token for an OAuth credential — same code.
MELTWATER_MCP_URL = os.environ.get("MELTWATER_MCP_URL", "https://api.meltwater.com/v2/mcp")
MELTWATER_API_TOKEN = os.environ.get("MELTWATER_API_TOKEN")
# ---------------------------------------------------------------------------


def require_anthropic_credentials():
    """Fail early, clearly, if no Anthropic API key is set.

    The Anthropic Python SDK authenticates from ANTHROPIC_API_KEY (or ANTHROPIC_AUTH_TOKEN). It
    does NOT read the Claude Code / `ant` CLI OAuth profile — that auto-resolution only happens
    inside the Claude Code runtime, not in a standalone script. So a `uv run` of this file needs a
    real API key even if you're logged into Claude Code. `anthropic.AsyncAnthropic()` with no args
    picks up whichever of these env vars is set.
    """
    if os.getenv("ANTHROPIC_API_KEY") or os.getenv("ANTHROPIC_AUTH_TOKEN"):
        return
    sys.exit(
        "No Anthropic API key found. Get one at https://console.anthropic.com "
        "(Settings -> API Keys), then run:\n"
        '  export ANTHROPIC_API_KEY="sk-ant-..."'
    )

# The Meltwater connector exposes many tools; the brief needs only these three. We attach just
# this allow-list so the run is deterministic and the model's context stays lean. Keep this in
# sync with the TOOLS block in build_instruction(). If your endpoint names them differently,
# edit here — run() falls back to attaching everything (with a warning) if nothing matches.
BRIEF_TOOLS = {
    "unified_retrieval_statistics_retrieval_tool",  # volume-by-day, sentiment, top sources
    "unified_retrieval_document_retrieval_tool",    # earned headlines + earned/UGC/competitor posts
    "unified_retrieval_query_gen_tool",             # plain-English -> boolean (fallback only)
}


INSTRUCTION_PATH = Path(__file__).with_name("scan_instruction.md")


def build_instruction(brand: dict) -> str:
    """Fill the scan-instruction template (scan_instruction.md) from the brand config.

    The prompt lives in its own file for readability; it uses $-style placeholders
    (string.Template) so the JSON example inside it stays literal, un-escaped braces.
    """
    ss = brand.get("savedSearches", {})
    floors = brand.get("floors", {})
    values = {
        "brand_name": brand.get("name"),
        "market": brand.get("market"),
        "brand_search": ss.get("brand"),
        "competitor_search": ss.get("competitors"),
        "competitors": ", ".join(brand.get("competitors", [])) or "(none configured)",
        "platforms": ", ".join(brand.get("platforms", [])),
        "confidential": brand.get("distribution", {}).get("confidential", ""),
        "twitter_views": floors.get("twitter_views"),
        "instagram_views": floors.get("instagram_views"),
        "tiktok_views": floors.get("tiktok_views"),
        "facebook_reach": floors.get("facebook_reach"),
        "reddit_reach": floors.get("reddit_reach"),
        "other_reach": floors.get("other_reach"),
    }
    template = Template(INSTRUCTION_PATH.read_text(encoding="utf-8"))
    return template.substitute(values)


async def open_session(stack, url, headers=None):
    """Open an in-process MCP client session to `url`. Tools execute client-side."""
    read, write, _ = await stack.enter_async_context(
        streamablehttp_client(url, headers=headers or {})
    )
    session = await stack.enter_async_context(ClientSession(read, write))
    await session.initialize()
    return session


def parse_brief(text: str) -> dict:
    """Extract the JSON BRIEF from the model's final message (tolerates fences/prose)."""
    t = text.strip()
    if t.startswith("```"):
        t = t.split("```", 2)[1].lstrip("json").strip() if "```" in t[3:] else t
    start, end = t.find("{"), t.rfind("}")
    if start == -1 or end == -1:
        raise ValueError(f"No JSON object found in model output:\n{text[:500]}")
    return json.loads(t[start:end + 1])


async def run(brand_path: str, out_path: str):
    require_anthropic_credentials()
    if not MELTWATER_API_TOKEN:
        raise SystemExit(
            "MELTWATER_API_TOKEN not set. Add your Meltwater MCP API token to .env "
            'or export it:\n  export MELTWATER_API_TOKEN="…"'
        )
    brand = json.loads(Path(brand_path).read_text())
    log(f"\n▸ Exec Media Brief — {brand.get('name')}  ({Path(brand_path).name})")

    # No api_key argument: the SDK reads ANTHROPIC_API_KEY / ANTHROPIC_AUTH_TOKEN from the env.
    # Never hardcode a key — it would ship with the file.
    client = anthropic.AsyncAnthropic()
    async with AsyncExitStack() as stack:
        # External signal — governed + metered. Bearer auth via the v2 MCP API token.
        log("▸ Connecting to Meltwater MCP…")
        meltwater = await open_session(
            stack, MELTWATER_MCP_URL,
            headers={"Authorization": f"Bearer {MELTWATER_API_TOKEN}"},
        )
        # Attach only the tools the brief needs (see BRIEF_TOOLS). Fall back to all tools —
        # loudly — if none match, so a name change at the endpoint degrades gracefully in a demo
        # rather than silently producing an empty brief.
        listed = await meltwater.list_tools()
        selected = [t for t in listed.tools if t.name in BRIEF_TOOLS]
        if not selected:
            available = ", ".join(t.name for t in listed.tools[:12])
            log(f"  WARN: none of BRIEF_TOOLS matched the connector. Attaching all "
                f"{len(listed.tools)} tools. Available: {available}...")
            selected = listed.tools
        log(f"▸ Tools ready: {', '.join(t.name for t in selected)}")
        tools = [async_mcp_tool(t, meltwater) for t in selected]

        runner = client.beta.messages.tool_runner(
            model=MODEL,
            max_tokens=16000,
            thinking={"type": "adaptive"},  # let the model reason across tool calls as needed
            messages=[{"role": "user", "content": build_instruction(brand)}],
            tools=tools,
        )
        log("▸ Collecting from Meltwater — the agent decides what to pull:")
        final = None
        calls = 0
        async for message in runner:
            final = message  # loop ends on the assistant turn carrying the finished BRIEF
            tool_uses = [b for b in message.content if getattr(b, "type", None) == "tool_use"]
            if tool_uses:
                for b in tool_uses:
                    calls += 1
                    log(f"   {calls:>2}. {b.name}  {_summarise_input(b.input)}")
            elif any(getattr(b, "type", None) == "thinking" for b in message.content):
                log("      · thinking…")
        log(f"▸ Collection done — {calls} Meltwater call(s). Assembling the brief…")

    text = "".join(b.text for b in final.content if getattr(b, "type", None) == "text")
    brief = parse_brief(text)
    n_items = sum(len(s.get("items") or []) for s in brief.get("sections", []))
    log(f"▸ Brief assembled: {len(brief.get('sections', []))} sections, {n_items} items. Rendering…")

    render.render_to_file(brief, brand, out_path)
    # Delivery is intentionally left to you: the deliverable is the HTML file above. To run this
    # headless every morning, schedule it and add a delivery step here — post to Slack, email it,
    # or drop it on a file host. See README ("Adapt it to your use case").


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Generate an executive daily media brief.")
    ap.add_argument("--brand", default=os.environ.get("BRAND_CONFIG", "brands/example-brand.json"))
    ap.add_argument("--out", default="brief.html")
    args = ap.parse_args()
    asyncio.run(run(args.brand, args.out))
