"""Reputation Watchdog — standalone reference agent on Meltwater MCP.

Runs a brand reputation scan: compare coverage in a window to the ~30-day norm, flag anomalies,
cross-reference the company's OWN first-party data, and draft a fused alert. Meltwater is one
governed source; the fusion with private first-party data happens here, in your own agent.

    SCAN (Meltwater MCP, grounded on a saved search)
      + FIRST-PARTY (your own data, client-side MCP)
      -> FUSE (the LLM reasons across both)  ->  ALERT (markdown)

Why client-side MCP: both sources are attached as in-process MCP clients (via the Anthropic SDK
tool runner), so the agent can reach a PRIVATE internal source (here, a mock) without exposing
it publicly. That fusion is the thing the Meltwater app can't do — and the reason to build your
own agent. See README.md.

Auth: needs a Meltwater v2 MCP API token (AUTH SEAM below) and Anthropic credentials
(ANTHROPIC_API_KEY, or ANTHROPIC_AUTH_TOKEN).

Draft reference code — confirm SDK calls against installed versions before external use.
"""

import argparse
import asyncio
import json
import os
import sys
from contextlib import AsyncExitStack
from datetime import datetime, timedelta, timezone
from pathlib import Path
from string import Template

import anthropic
from anthropic.lib.tools.mcp import async_mcp_tool
from dotenv import load_dotenv
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

# Load a local .env if present. Does NOT override variables already exported in the shell.
load_dotenv()

MODEL = "claude-opus-4-8"


def log(msg: str = ""):
    """Progress line to stderr, flushed so it appears live during a run/demo."""
    print(msg, file=sys.stderr, flush=True)


def _summarise_input(inp) -> str:
    if not isinstance(inp, dict):
        return ""
    interesting = ("query", "savedSearchIds", "saved_search_ids", "savedSearchId", "sortBy",
                   "sort_by", "metric", "start", "end", "startDate", "endDate", "region", "regions")
    parts = [f"{k}={inp[k]}" for k in interesting if inp.get(k) not in (None, "", [])]
    summary = ", ".join(parts) if parts else ", ".join(list(inp.keys())[:4])
    return f"({summary[:90]})"


# --- AUTH SEAM -------------------------------------------------------------
# Meltwater auth is a single seam: set MELTWATER_API_TOKEN (v2 MCP API-token auth) and the agent
# runs end-to-end. When per-user OAuth clients land, swap the static token — same code.
MELTWATER_MCP_URL = os.environ.get("MELTWATER_MCP_URL", "https://api.meltwater.com/v2/mcp")
MELTWATER_API_TOKEN = os.environ.get("MELTWATER_API_TOKEN")
FIRST_PARTY_MCP_URL = os.environ.get("MOCK_FIRSTPARTY_URL", "http://localhost:8765/mcp")
# ---------------------------------------------------------------------------

# The connector exposes many tools; the scan needs only retrieval + a saved-search LIST tool (for
# the Step-1 resolution demo). Attach just these so the run is deterministic. List-tool names vary
# by connector, so we include the common candidates and attach whichever match; run() falls back
# to all Meltwater tools (loudly) if none do. First-party tools are always attached in full.
MELTWATER_TOOLS = {
    "unified_retrieval_statistics_retrieval_tool",
    "unified_retrieval_document_retrieval_tool",
    "unified_retrieval_query_gen_tool",
    "list_searches_metadata",
    "listening_list_searches",
    "explore_plus_list_searches",
}

INSTRUCTION_PATH = Path(__file__).with_name("scan_instruction.md")


def require_anthropic_credentials():
    """Fail early if no Anthropic creds. The SDK reads ANTHROPIC_API_KEY / ANTHROPIC_AUTH_TOKEN —
    NOT the Claude Code / `ant` CLI OAuth login."""
    if os.getenv("ANTHROPIC_API_KEY") or os.getenv("ANTHROPIC_AUTH_TOKEN"):
        return
    sys.exit(
        "No Anthropic API key found. Get one at https://console.anthropic.com "
        "(Settings -> API Keys), then run:\n"
        '  export ANTHROPIC_API_KEY="sk-ant-..."'
    )


def compute_windows(cfg: dict, as_of_arg: str | None) -> dict:
    """Anchor the scan to an 'as-of' day and derive the anomaly window + baseline in Python (so
    the model never does fuzzy date arithmetic). --as-of overrides the config's asOf; both default
    to today. The as-of day IS 'today' for the scan: the anomaly window is the trailing
    windowHours ending at end-of-day; the baseline is the baselineDays before that window."""
    window_hours = int(cfg.get("windowHours", 24))
    baseline_days = int(cfg.get("baselineDays", 30))
    # CLI --as-of overrides the config's asOf; both default to today. Treat the common "no date"
    # sentinels (absent, JSON null -> None, or the strings "null"/"none"/"today"/"now"/"") as today,
    # so a config typo like "asOf": "null" doesn't crash or get parsed as a date.
    as_of_str = as_of_arg if as_of_arg is not None else cfg.get("asOf")
    if isinstance(as_of_str, str):
        as_of_str = as_of_str.strip()
    backdated = bool(as_of_str) and str(as_of_str).lower() not in ("null", "none", "today", "now", "")
    as_of_day = (datetime.strptime(as_of_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                 if backdated else datetime.now(timezone.utc))

    window_end = (as_of_day + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    window_start = window_end - timedelta(hours=window_hours)
    baseline_start = window_start - timedelta(days=baseline_days)
    fmt = "%Y-%m-%d %H:%M UTC"
    return {
        "as_of": as_of_day.strftime("%Y-%m-%d"),
        "is_backdated": backdated,
        "window_start": window_start.strftime(fmt),
        "window_end": window_end.strftime(fmt),
        "baseline_start": baseline_start.strftime(fmt),
        "window_hours": window_hours,
        "baseline_days": baseline_days,
    }


def build_scan_instruction(cfg: dict, win: dict) -> str:
    ss = cfg.get("savedSearch", {})
    fp = cfg.get("firstParty", {})
    values = {
        "name": cfg.get("name"),
        "brand": cfg.get("brand"),
        "saved_search_id": ss.get("id"),
        "saved_search_name": ss.get("name"),
        "first_party_label": fp.get("label", "first-party source"),
        "first_party_tool": fp.get("signalTool", "get_support_signal"),
        "regions": ", ".join(cfg.get("regions", [])) or "(any)",
        "as_of": win["as_of"],
        "window_start": win["window_start"],
        "window_end": win["window_end"],
        "baseline_start": win["baseline_start"],
        "baseline_days": win["baseline_days"],
    }
    return Template(INSTRUCTION_PATH.read_text(encoding="utf-8")).substitute(values)


async def open_session(stack, url, headers=None):
    """Open an in-process MCP client session to `url`. Tools execute client-side — so a
    private/internal URL (localhost, VPC) is reachable; nothing is exposed publicly."""
    read, write, _ = await stack.enter_async_context(
        streamablehttp_client(url, headers=headers or {})
    )
    session = await stack.enter_async_context(ClientSession(read, write))
    await session.initialize()
    return session


async def run(watch_path: str, as_of_arg: str | None, out_path: str):
    require_anthropic_credentials()
    if not MELTWATER_API_TOKEN:
        raise SystemExit(
            "MELTWATER_API_TOKEN not set. Add your Meltwater v2 MCP API token to .env "
            'or export it:\n  export MELTWATER_API_TOKEN="…"'
        )
    cfg = json.loads(Path(watch_path).read_text())
    win = compute_windows(cfg, as_of_arg)
    tag = f"as of {win['as_of']}" + (" (backdated)" if win["is_backdated"] else " (today)")
    log(f"\n▸ Reputation Watchdog — {cfg.get('brand')} · {cfg.get('name')}  [{tag}]")

    client = anthropic.AsyncAnthropic()  # reads ANTHROPIC_API_KEY / ANTHROPIC_AUTH_TOKEN from env
    async with AsyncExitStack() as stack:
        log("▸ Connecting to Meltwater MCP (external signal)…")
        meltwater = await open_session(
            stack, MELTWATER_MCP_URL,
            headers={"Authorization": f"Bearer {MELTWATER_API_TOKEN}"},
        )
        log(f"▸ Connecting to first-party source ({cfg.get('firstParty', {}).get('label')})…")
        first_party = await open_session(stack, FIRST_PARTY_MCP_URL)

        mw_listed = await meltwater.list_tools()
        mw_tools = [t for t in mw_listed.tools if t.name in MELTWATER_TOOLS]
        if not mw_tools:
            log(f"  WARN: none of MELTWATER_TOOLS matched. Attaching all {len(mw_listed.tools)}.")
            mw_tools = mw_listed.tools
        fp_listed = await first_party.list_tools()  # attach the private source's tools in full
        tools = ([async_mcp_tool(t, meltwater) for t in mw_tools]
                 + [async_mcp_tool(t, first_party) for t in fp_listed.tools])
        log(f"▸ Tools ready: {', '.join(t.name for t in mw_tools)} "
            f"+ first-party [{', '.join(t.name for t in fp_listed.tools)}]")

        runner = client.beta.messages.tool_runner(
            model=MODEL,
            max_tokens=4096,
            thinking={"type": "adaptive"},  # reason across the two sources
            messages=[{"role": "user", "content": build_scan_instruction(cfg, win)}],
            tools=tools,
        )
        log("▸ Scanning + fusing — the agent decides what to pull:")
        final, calls = None, 0
        async for message in runner:
            final = message
            for b in [b for b in message.content if getattr(b, "type", None) == "tool_use"]:
                calls += 1
                log(f"   {calls:>2}. {b.name}  {_summarise_input(b.input)}")
        log(f"▸ Scan done — {calls} tool call(s). Alert ready.")

    alert = "".join(b.text for b in final.content if getattr(b, "type", None) == "text").strip()
    Path(out_path).write_text(alert + "\n", encoding="utf-8")
    log(f"▸ Alert written to {out_path}")
    print("\n" + alert)  # the deliverable — to stdout for piping / reading
    # Delivery is intentionally left to you: the deliverable is the markdown above (--out) and
    # stdout. To run this headless, add a delivery step here — post to your channel, email it, etc.


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Run a reputation scan fused with first-party data.")
    ap.add_argument("--watch", default=os.environ.get("WATCH_CONFIG", "watches/example-watch.json"))
    ap.add_argument("--as-of", dest="as_of", default=None,
                    help="Anchor the scan to a date (YYYY-MM-DD). Overrides the config; default = today.")
    ap.add_argument("--out", default="brief.md")
    args = ap.parse_args()
    asyncio.run(run(args.watch, args.as_of, args.out))
