"""Mock first-party MCP server — stands in for your OWN system.

This is the second source in the fusion: in a real deployment you'd replace it with a
connector to your support desk / CRM / claims system. Here it serves illustrative
support-contact data for the Toyota example so the agent can demonstrate the join.

Run standalone:   uv run python mock_firstparty/server.py
An MCP client (e.g. Claude Code) can also launch this locally as an MCP server.

Draft — confirm FastMCP transport/version against your installed `mcp` package.
"""

import json
from datetime import date, datetime
from pathlib import Path

from mcp.server.fastmcp import FastMCP

# Port matches MOCK_FIRSTPARTY_URL in the agent (.env.example default: localhost:8765).
mcp = FastMCP("support_desk", port=8765)
DATA = json.loads((Path(__file__).parent / "support_data.json").read_text())


def _regime_for(as_of: str = "") -> str:
    """Which support regime applies on the scan's as-of date: 'incident' during the recall
    episode's active window, else 'baseline'. Empty/invalid as_of = today (real-time)."""
    win = DATA["incident"]["active_window"]
    try:
        d = datetime.strptime(as_of.strip(), "%Y-%m-%d").date() if as_of and as_of.strip() else date.today()
    except ValueError:
        d = date.today()
    start = datetime.strptime(win["start"], "%Y-%m-%d").date()
    end = datetime.strptime(win["end"], "%Y-%m-%d").date()
    return "incident" if start <= d <= end else "baseline"


@mcp.tool()
def get_support_signal(issue: str, as_of: str = "", days: int = 10) -> dict:
    """Return first-party support-contact signal for an issue, by region, AS OF a date.

    ILLUSTRATIVE DATA — stands in for your real internal system. Returns the elevated
    signal only when `as_of` falls inside the 26 May 2026 recall episode; otherwise it returns a
    quiet baseline (so a normal-day scan fuses to a genuine all-clear, not a stale spike).

    Args:
        issue:  the topic to match (e.g. "stall", "loss of power").
        as_of:  the scan's anchor date (YYYY-MM-DD). Empty = today (real-time).
        days:   lookback window in days.
    """
    regime = _regime_for(as_of)
    return {
        "issue": issue,
        "as_of": as_of or "today",
        "window_days": days,
        "regime": regime,  # "incident" or "baseline"
        "note": "ILLUSTRATIVE — replace with your real support/CRM source in production",
        "signal": DATA[regime],
    }


if __name__ == "__main__":
    # HTTP so the standalone agent can attach it as a client-side MCP client over localhost.
    # For MCP-client local use, stdio also works: mcp.run(transport="stdio")
    mcp.run(transport="streamable-http")
