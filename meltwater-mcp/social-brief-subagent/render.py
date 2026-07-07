"""Deterministic renderer:  CAMPAIGN BRIEF (+ campaign config) -> flat static HTML.

Your orchestrator (social_brief_subagent.py) turns the Meltwater insight payload into a
CAMPAIGN BRIEF dict. This module turns that dict into a single self-contained HTML file, using
brief_template.html as the shell. Nothing here calls an LLM or the network — it is pure,
testable, and safe to fork.

    INSIGHT (Meltwater sub-agent)  ->  BRIEF (your agent, dict)  ->  RENDER (this file)

Every field is optional-safe and escaped, so a thin BRIEF still renders a valid page rather
than crashing.
"""

from __future__ import annotations

import html
import json
import os
from pathlib import Path

TEMPLATE_PATH = Path(__file__).with_name("brief_template.html")

# Which theme keys the campaign config may set, and the CSS var each maps to.
_THEME_KEYS = {
    "primary": "--primary",
    "primaryHi": "--primary-hi",
    "accent": "--accent",
    "ink": "--ink",
    "surface": "--surface",
    "page": "--page",
    "card": "--card",
    "cardAlt": "--card-alt",
    "fontDisplay": "--font-display",
    "fontBody": "--font-body",
}


# ── helpers ────────────────────────────────────────────────────────────────
def esc(v) -> str:
    return html.escape(str(v), quote=True) if v is not None else ""


def _link(text, url) -> str:
    t = esc(text)
    if url:
        return f'<a href="{esc(url)}" target="_blank" rel="noopener">{t}</a>'
    return t


def _sec_title(num: str, title: str, count: str = "") -> str:
    pn = f'<span class="pn">{esc(num)}</span>' if num else ""
    c = f'<span class="count">{esc(count)}</span>' if count else ""
    return (f'    <div class="sec-title"><span class="pill">{pn}{esc(title)}</span>'
            f'<span class="ln"></span>{c}</div>')


# ── validation (light; warns, never crashes) ───────────────────────────────
def validate(brief: dict) -> list[str]:
    warnings: list[str] = []
    for f in ("meta", "conceptName", "strategicSummary", "concepts"):
        if f not in brief:
            warnings.append(f"missing top-level field '{f}'")
    if not brief.get("insightFoundation"):
        warnings.append("no insightFoundation — the Meltwater grounding won't be visible")
    for i, c in enumerate(brief.get("concepts") or []):
        if not c.get("groundedIn"):
            warnings.append(f"concept[{i}] '{c.get('name','?')}' has no groundedIn — is it traceable to an insight?")
    return warnings


# ── section renderers ───────────────────────────────────────────────────────
def _render_masthead(brief: dict, cfg: dict) -> str:
    meta = brief.get("meta", {})
    logo = cfg.get("logoUrl")
    wordmark = cfg.get("wordmark") or cfg.get("brand") or meta.get("brand") or ""
    mark = (f'<img class="wm" src="{esc(logo)}" alt="{esc(wordmark)}">'
            if logo else f'<span class="wm-text">{esc(wordmark)}</span>')
    meta_bits = " · ".join(esc(x) for x in (
        meta.get("market"), meta.get("audienceLabel"), meta.get("dateLong")) if x)
    obj = meta.get("objective")
    obj_html = f'<div class="mast-obj"><b>Brief:</b> {esc(obj)}</div>' if obj else ""
    return f"""  <div class="mast">
    <div class="mast-line">{mark}<span class="kind">Campaign Insight Brief</span></div>
    <div class="mast-meta">{meta_bits}</div>
    {obj_html}
  </div>"""


def _render_concept_hero(brief: dict) -> str:
    name = brief.get("conceptName")
    if not name:
        return ""
    return f"""  <div class="concept-hero">
    <div class="lab">The big idea</div>
    <h1>{esc(name)}</h1>
  </div>"""


def _render_summary(brief: dict) -> str:
    s = brief.get("strategicSummary")
    if not s:
        return ""
    return (_sec_title("01", "Strategic summary")
            + f'\n    <p class="summary">{esc(s)}</p>')


def _render_insight_foundation(brief: dict) -> str:
    items = brief.get("insightFoundation") or []
    body_title = _sec_title("02", "Grounded in Meltwater insights", f"{len(items)} signals")
    if not items:
        return body_title + '\n    <p class="empty">No insight foundation supplied.</p>'
    rows = []
    for i, it in enumerate(items, 1):
        rows.append(f"""      <div class="ins">
        <div class="n">{i:02d}</div>
        <div><div class="it">{esc(it.get('insight'))}</div>
          <div class="sw">{esc(it.get('soWhat'))}</div></div>
      </div>""")
    panel = (f'    <div class="insight-panel">\n'
             f'      <div class="ptag"><span class="dot"></span>Meltwater Insight Sub-Agent</div>\n'
             + "\n".join(rows) + "\n    </div>")
    return body_title + "\n" + panel


def _render_concepts(brief: dict) -> str:
    items = brief.get("concepts") or []
    title = _sec_title("03", "Campaign concepts", f"{len(items)}")
    if not items:
        return title + '\n    <p class="empty">No concepts.</p>'
    cards = []
    for c in items:
        fmt_rows = []
        for f in (c.get("formats") or []):
            form = (f' <span class="form">· {esc(f.get("format"))}</span>'
                    if f.get("format") else "")
            fmt_rows.append(
                f'<div class="fmt"><div class="pf">{esc(f.get("platform"))}</div>'
                f'<div class="idea">{esc(f.get("idea"))}{form}</div></div>'
            )
        formats = "".join(fmt_rows)
        tags = "".join(f'<span class="tag">{esc(t)}</span>' for t in (c.get("hashtags") or []))
        grounded = (f'<div class="grounded"><b>Grounded in:</b> {esc(c.get("groundedIn"))}</div>'
                    if c.get("groundedIn") else "")
        why = f'<p class="why">{esc(c.get("why"))}</p>' if c.get("why") else ""
        cards.append(f"""    <div class="ccard">
      <h3>{esc(c.get('name'))}</h3>
      <p class="big">{esc(c.get('bigIdea'))}</p>
      {why}{grounded}
      {f'<div class="formats">{formats}</div>' if formats else ''}
      {f'<div class="tags">{tags}</div>' if tags else ''}
    </div>""")
    return title + f'\n    <div class="concepts">\n{chr(10).join(cards)}\n    </div>'


def _render_channel_plan(brief: dict) -> str:
    items = brief.get("channelPlan") or []
    if not items:
        return ""
    rows = "".join(
        f'<tr><td class="c1">{esc(r.get("channel"))}</td>'
        f'<td class="c2">{esc(r.get("role"))}</td>'
        f'<td class="c3">{esc(r.get("note"))}</td></tr>'
        for r in items
    )
    return _sec_title("04", "Channel plan") + f'\n    <table class="chan">{rows}</table>'


def _render_timing(brief: dict) -> str:
    t = brief.get("timingHook")
    if not t:
        return ""
    return (_sec_title("05", "Why now")
            + f'\n    <div class="timing"><div class="lab">Timing hook</div><p>{esc(t)}</p></div>')


def _render_watchouts(brief: dict) -> str:
    items = brief.get("watchouts") or []
    if not items:
        return ""
    lis = "".join(f"<li>{esc(x)}</li>" for x in items)
    return _sec_title("06", "Watch-outs") + f'\n    <ul class="watch">{lis}</ul>'


def _render_sources(brief: dict) -> str:
    items = brief.get("sources") or []
    title = _sec_title("07", "Evidence", "via Meltwater")
    if not items:
        return title + '\n    <p class="empty">No sources supplied.</p>'
    lis = []
    for s in items:
        outlet = f'<span class="src-o">{esc(s.get("outlet"))}</span>' if s.get("outlet") else ""
        metric = f'<span class="src-m">{esc(s.get("metric"))}</span>' if s.get("metric") else ""
        lis.append(f'      <li>{_link(s.get("title"), s.get("url"))} {outlet}{metric}</li>')
    return title + '\n    <ul class="sources">\n' + "\n".join(lis) + "\n    </ul>"


def _render_footer(brief: dict, cfg: dict) -> str:
    meta = brief.get("meta", {})
    left = " · ".join(esc(x) for x in (
        meta.get("confidential"),
        meta.get("source") or "Meltwater",
        meta.get("searchLabel"),
        meta.get("market"),
    ) if x)
    right = esc(cfg.get("brand") or meta.get("brand") or "")
    return f'  <div class="foot"><span class="fl">{left}</span><span class="fr">{right}</span></div>'


# ── theme injection ────────────────────────────────────────────────────────
def _brand_tokens(cfg: dict) -> str:
    theme = cfg.get("theme", {})
    decls = [f"{var}:{theme[key]};" for key, var in _THEME_KEYS.items() if theme.get(key)]
    return f":root{{{''.join(decls)}}}" if decls else ""


# ── public entry point ──────────────────────────────────────────────────────
def render(brief: dict, cfg: dict, template_path: Path = TEMPLATE_PATH) -> str:
    template = template_path.read_text(encoding="utf-8")

    parts = [
        _render_masthead(brief, cfg),
        _render_concept_hero(brief),
        '  <div class="pad">',
        _render_summary(brief),
        _render_insight_foundation(brief),
        _render_concepts(brief),
        _render_channel_plan(brief),
        _render_timing(brief),
        _render_watchouts(brief),
        _render_sources(brief),
        "  </div>",
        _render_footer(brief, cfg),
    ]
    body = "\n".join(p for p in parts if p)

    meta = brief.get("meta", {})
    title = (f"{cfg.get('brand') or meta.get('brand') or 'Campaign'} · Campaign Insight Brief"
             f"{' — ' + meta.get('dateLong') if meta.get('dateLong') else ''}")

    return (template
            .replace("{{TITLE}}", esc(title))
            .replace("{{BRAND_TOKENS}}", _brand_tokens(cfg))
            .replace("{{REPORT_BODY}}", body))


def render_to_file(brief: dict, cfg: dict, out_path: str,
                   template_path: Path = TEMPLATE_PATH) -> str:
    for w in validate(brief):
        print(f"WARN: {w}")
    out = render(brief, cfg, template_path)
    Path(out_path).write_text(out, encoding="utf-8")
    print(f"OK: {len(out):,} bytes -> {out_path}")
    return out_path


# ── CLI: render a BRIEF json + campaign config to HTML (handy for template work) ─
if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="Render a CAMPAIGN BRIEF json to a flat HTML brief.")
    ap.add_argument("brief", help="path to a CAMPAIGN BRIEF json file")
    ap.add_argument("--campaign", default=os.environ.get("CAMPAIGN_CONFIG", "campaigns/example-campaign.json"))
    ap.add_argument("--out", default="brief.html")
    args = ap.parse_args()
    brief = json.loads(Path(args.brief).read_text())
    cfg = json.loads(Path(args.campaign).read_text())
    render_to_file(brief, cfg, args.out)
