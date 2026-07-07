# Meltwater API Examples

Example code for Meltwater API and MCP customers building their own solutions for PR & marketing use cases.

## Documentation

For the full API reference, guides, and help, visit the **Meltwater Developer Portal** at
[developer.meltwater.com](https://developer.meltwater.com). This repository provides runnable
examples to complement that documentation.

## Repository structure

Examples are grouped by the Meltwater product they use, then by use case:

```text
meltwater-mcp/
  <use-case>/
```

## Examples

**Meltwater MCP (reference agents)**

- [`meltwater-mcp/exec-media-brief`](meltwater-mcp/exec-media-brief) — a reference
  agent that uses Meltwater MCP to produce a branded, exec-ready daily media brief
  (news + social), rendered to a self-contained HTML file. Runnable headless as a
  standalone Python script or no-code via an MCP client.
- [`meltwater-mcp/social-brief-subagent`](meltwater-mcp/social-brief-subagent) — a reference
  agent showing how to plug Meltwater MCP into your *own* agent as a specialist insight
  sub-agent: your orchestrator asks Meltwater for a grounded landscape insight, then authors
  a social campaign brief from it (rendered to a self-contained HTML file). Runnable
  standalone or no-code via an MCP client.
- [`meltwater-mcp/reputation-watchdog`](meltwater-mcp/reputation-watchdog) — a reference
  agent that scans a brand's coverage for an anomaly vs its 30-day norm and **fuses it with
  your own first-party data** (via client-side MCP) into a single alert — showing how to join
  Meltwater with a private internal source in your own agent. Runnable standalone or no-code
  via an MCP client.
