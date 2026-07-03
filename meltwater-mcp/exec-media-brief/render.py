"""Deterministic renderer:  BRIEF (+ brand config) -> flat static HTML.

The agent (exec_media_brief.py) collects from Meltwater and assembles a BRIEF dict.
This module turns that dict into a single self-contained HTML file, using
brief_template.html as the shell. Nothing here calls an LLM or a network — it is
pure, testable, and safe to fork.

Design split:
    COLLECT (agent, Meltwater MCP)  ->  BRIEF (dict)  ->  RENDER (this file)

Everything is escaped and every field is optional-safe, so a thin BRIEF still
renders a valid page rather than crashing.
"""

from __future__ import annotations

import html
import json
import os
from pathlib import Path

TEMPLATE_PATH = Path(__file__).with_name("brief_template.html")

# Which theme keys the brand config may set, and the CSS var each maps to.
_THEME_KEYS = {
    "primary": "--primary",
    "primaryHi": "--primary-hi",
    "ink": "--ink",
    "accentWarm": "--accent-warm",
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


def _headline(text, url) -> str:
    t = esc(text)
    if url:
        return f'<a class="hl" href="{esc(url)}" target="_blank" rel="noopener">{t}</a>'
    return t


def _dominant(pos, neu, neg):
    """Return (key, pct) for the largest sentiment bucket."""
    buckets = {"pos": pos or 0, "neu": neu or 0, "neg": neg or 0}
    key = max(buckets, key=buckets.get)
    return key, buckets[key]


# ── validation (light; warns, never crashes) ───────────────────────────────
def validate(brief: dict) -> list[str]:
    warnings: list[str] = []
    for f in ("meta", "execSummary", "sentiment", "sections"):
        if f not in brief:
            warnings.append(f"missing top-level field '{f}'")

    es = (brief.get("execSummary") or "").strip()
    if es:
        import re
        n = len([s for s in re.split(r"(?<=[.!?])\s+", es) if s.strip()])
        if n > 3:
            warnings.append(f"execSummary has {n} sentences — style guide is max 3")

    sent = brief.get("sentiment", {})
    ov = sent.get("overall", {})
    if ov and (ov.get("pos", 0) + ov.get("neu", 0) + ov.get("neg", 0)) not in (0, 100):
        warnings.append("sentiment.overall pos+neu+neg != 100")
    for i, p in enumerate(sent.get("platforms", [])):
        if (p.get("pos", 0) + p.get("neu", 0) + p.get("neg", 0)) not in (0, 100):
            warnings.append(f"sentiment.platforms[{i}] ({p.get('label','?')}) pos+neu+neg != 100")
    return warnings


# ── section body renderers ─────────────────────────────────────────────────
def _render_masthead(brief: dict, brand: dict) -> str:
    meta = brief.get("meta", {})
    logo = brand.get("logoUrl")
    wordmark = brand.get("wordmark") or brand.get("name") or meta.get("brandName") or ""
    mark = (
        f'<img class="wm" src="{esc(logo)}" alt="{esc(wordmark)}">'
        if logo
        else f'<span class="wm-text">{esc(wordmark)}</span>'
    )

    ov = brief.get("sentiment", {}).get("overall", {})
    dom_key, dom_pct = _dominant(ov.get("pos"), ov.get("neu"), ov.get("neg"))
    dom_label = {"pos": "overall positive", "neu": "overall neutral", "neg": "overall negative"}[dom_key]
    dom_class = {"pos": "glance-pos", "neu": "", "neg": "glance-neg"}[dom_key]
    others = {"pos": [("neu", ov.get("neu")), ("neg", ov.get("neg"))],
              "neu": [("pos", ov.get("pos")), ("neg", ov.get("neg"))],
              "neg": [("pos", ov.get("pos")), ("neu", ov.get("neu"))]}[dom_key]
    sub = " · ".join(f"{v}% {k}" for k, v in others if v is not None)

    delta = ov.get("delta") or ""
    good = ov.get("deltaGood")
    dcls = "good" if good is True else "bad" if good is False else ""

    glance2 = ""
    if ov:
        glance2 = f"""
      <div class="glance {dom_class}">
        <div class="g-big">{esc(dom_pct)}%</div>
        <div class="g-sub">{esc(dom_label)}</div>
        <div class="g-d">{esc(sub)}</div>
      </div>"""

    glance1 = ""
    if ov.get("volume") is not None:
        glance1 = f"""
      <div class="glance">
        <div class="g-big">{esc(ov.get('volume'))}</div>
        <div class="g-sub">signals today</div>
        <div class="g-d {dcls}">{esc(delta)}</div>
      </div>"""

    return f"""  <div class="mast">
    <div>
      <div class="mast-line">{mark}<h1>Daily Brief</h1></div>
      <div class="mast-meta">{esc(meta.get('dateLong'))}</div>
    </div>
    <div class="glance-row">{glance1}{glance2}
    </div>
  </div>"""


def _render_sentiment(brief: dict) -> str:
    sent = brief.get("sentiment", {})
    tiles = []
    for p in sent.get("platforms", []):
        pos, neu, neg = p.get("pos", 0), p.get("neu", 0), p.get("neg", 0)
        dom_key, dom_pct = _dominant(pos, neu, neg)
        big_cls = {"pos": "t-pos", "neu": "t-neu", "neg": "t-neg"}[dom_key]
        dom_word = {"pos": "positive", "neu": "neutral", "neg": "negative"}[dom_key]
        delta = p.get("delta") or ""
        good = p.get("deltaGood")
        dcls = "good" if good is True else "bad" if good is False else "flat"
        tiles.append(f"""    <div class="tile">
      <div class="t-name">{esc(p.get('label'))}</div>
      <div class="t-vol">{esc(p.get('volume'))}</div>
      <div class="t-big {big_cls}">{esc(dom_pct)}%</div>
      <div class="t-dom">{dom_word}</div>
      <div class="t-bar"><div class="sbar"><i class="pos" style="width:{pos}%"></i><i class="neu" style="width:{neu}%"></i><i class="neg" style="width:{neg}%"></i></div></div>
      <div class="t-pct">{pos} · {neu} · {neg}</div>
      <div class="t-delta delta {dcls}">{esc(delta)}</div>
    </div>""")

    strip = sent.get("strip")
    strip_html = f'\n    <p class="strip-cap">{esc(strip)}</p>' if strip else ""
    if not tiles:
        return ""
    return f"""    <div class="sec-title"><span class="pill">Sentiment</span><span class="ln"></span><span class="count">last 24h</span></div>
    <div class="ptiles">
{chr(10).join(tiles)}
    </div>{strip_html}"""


def _render_empty(title: str, dek: str = "") -> str:
    return f"""    <div class="empty-card"><div class="mk"><svg viewBox="0 0 24 24"><circle cx="11" cy="11" r="7"/><line x1="16" y1="16" x2="21" y2="21"/></svg></div>
      <div><div class="ek">{esc(title)}</div><p>{esc(dek or 'Nothing qualified for this window.')}</p></div></div>"""


def _news_card(it: dict, wide: bool) -> str:
    cls = "scard scard--wide" if wide else "scard"
    img = it.get("img")
    body_open = '<div class="scard-body">' if wide else ""
    body_close = "</div>" if wide else ""
    img_html = ""
    if img:
        img_cls = "scard-img-side" if wide else "scard-img"
        img_html = f'<img class="{img_cls}" src="{esc(img)}" alt="">'
    kicker = f'<span class="kick">{esc(it["kicker"])}</span>' if it.get("kicker") else ""
    out_bits = " · ".join(esc(x) for x in (it.get("outlet"), it.get("date"),
                          f"Reach {it['reach']}" if it.get("reach") else None) if x)
    return f"""    <div class="{cls}">{img_html}
      {body_open}{kicker}
      <h3>{_headline(it.get('headline'), it.get('url'))}</h3>
      <p class="dek">{esc(it.get('dek'))}</p>
      <div class="out">{out_bits}</div>{body_close}
    </div>"""


def _render_news(sec: dict) -> str:
    items = sec.get("items") or []
    if not items:
        return _render_empty(sec.get("title", "News"))
    parts = []
    rest = items
    hero = next((it for it in items if it.get("hero")), None)
    if hero:
        rest = [it for it in items if it is not hero]
        stats = "".join(
            f'<div class="s"><div class="k">{esc(s.get("k"))}</div><div class="v">{esc(s.get("v"))}</div></div>'
            for s in (hero.get("stats") or [])
        )
        quotes = "".join(
            f'<div class="qbox"><q>{esc(q.get("q"))}</q><div class="by">— {esc(q.get("by"))}</div></div>'
            for q in (hero.get("quotes") or [])
        )
        out_bits = " · ".join(esc(x) for x in (hero.get("outlet"), hero.get("date"),
                              f"Reach {hero['reach']}" if hero.get("reach") else None) if x)
        parts.append(f"""    <div class="hero-card"><div class="hc-body">
        <span class="kick">{esc(hero.get('kicker'))}</span>
        <h2>{_headline(hero.get('headline'), hero.get('url'))}</h2>
        <div class="out">{out_bits}</div>
        <p class="dek">{esc(hero.get('dek'))}</p>
        {f'<div class="quotes">{quotes}</div>' if quotes else ''}
        {f'<div class="statrow">{stats}</div>' if stats else ''}
      </div></div>""")
    if rest:
        cards = []
        for i, it in enumerate(rest):
            wide = (len(rest) % 2 == 1) and (i == len(rest) - 1)  # orphan spans full width
            cards.append(_news_card(it, wide))
        wrap = '<div style="margin-top:12px">' if hero else ""
        wrap_close = "</div>" if hero else ""
        parts.append(f'    {wrap}<div class="cardgrid">\n{chr(10).join(cards)}\n    </div>{wrap_close}')
    return "\n".join(parts)


def _social_card(it: dict, wide: bool) -> str:
    cls = "scard scard--wide" if wide else "scard"
    img = it.get("img")
    body_open = '<div class="scard-body">' if wide else ""
    body_close = "</div>" if wide else ""
    img_html = ""
    if img:
        img_cls = "scard-img-side" if wide else "scard-img"
        img_html = f'<img class="{img_cls}" src="{esc(img)}" alt="">'
    src = " · ".join(esc(x) for x in (it.get("platform"), it.get("handle")) if x)
    metrics = "".join(
        f'<div class="metric"><b>{esc(m.get("v"))}</b><span>{esc(m.get("k"))}</span></div>'
        for m in (it.get("metrics") or [])
    )
    out = " · ".join(esc(x) for x in (it.get("date"),) if x)
    return f"""    <div class="{cls}">{img_html}
      {body_open}<span class="kick">{src}</span>
      <h3>{_headline(it.get('headline'), it.get('url'))}</h3>
      <p class="dek">{esc(it.get('dek'))}</p>
      {f'<div class="metrics">{metrics}</div>' if metrics else ''}
      <div class="out">{out}</div>{body_close}
    </div>"""


def _render_social(sec: dict) -> str:
    items = sec.get("items") or []
    if not items:
        return _render_empty(sec.get("title", "Social"))
    cards = []
    for i, it in enumerate(items):
        wide = (len(items) % 2 == 1) and (i == len(items) - 1)
        cards.append(_social_card(it, wide))
    return f'    <div class="cardgrid">\n{chr(10).join(cards)}\n    </div>'


def _render_reddit(sec: dict) -> str:
    items = sec.get("items") or []
    if not items:
        return _render_empty(sec.get("title", "Reddit"))
    cards = []
    for it in items:
        hd = " · ".join(esc(x) for x in (it.get("sub"), it.get("date"), it.get("author"),
                        f"Reach {it['reach']}" if it.get("reach") else None) if x)
        quote = f'<div class="qline">{esc(it["quote"])}</div>' if it.get("quote") else ""
        eng = it.get("eng")
        eng_html = f'<div class="eng"><div class="n">{esc(eng)}</div><div class="l">eng</div></div>' if eng is not None else ""
        cards.append(f"""    <div class="reddit-card">{eng_html}
      <div class="body">
        <div class="hd">{hd}</div>
        <h3>{_headline(it.get('headline'), it.get('url'))}</h3>
        <p class="dek">{esc(it.get('dek'))}</p>{quote}
      </div>
    </div>""")
    return "\n".join(cards)


_KIND_RENDERERS = {
    "news": _render_news,
    "social": _render_social,
    "reddit": _render_reddit,
}


def _render_section(sec: dict) -> str:
    num = f'<span class="pn">{esc(sec["num"])}</span> ' if sec.get("num") else ""
    count = f'<span class="count">{esc(sec["count"])}</span>' if sec.get("count") else ""
    title = f"""    <div class="sec-title"><span class="pill">{num}{esc(sec.get('title'))}</span><span class="ln"></span>{count}</div>"""
    renderer = _KIND_RENDERERS.get(sec.get("kind", "news"), _render_news)
    return title + "\n" + renderer(sec)


def _render_bottomline(brief: dict) -> str:
    bl = brief.get("bottomLine")
    if not bl:
        return ""
    lis = "".join(f"<li>{esc(x) if not _has_bold(x) else _bold(x)}</li>" for x in bl)
    return f"""  <div class="pad"><div class="bottomline">
    <h2>Bottom line <span class="tk">at a glance</span></h2>
    <ul>{lis}</ul>
  </div></div>"""


def _has_bold(s: str) -> bool:
    return "**" in str(s)


def _bold(s: str) -> str:
    # very small **bold** -> <b> pass, everything else escaped
    import re
    out, last = [], 0
    for m in re.finditer(r"\*\*(.+?)\*\*", str(s)):
        out.append(esc(s[last:m.start()]))
        out.append(f"<b>{esc(m.group(1))}</b>")
        last = m.end()
    out.append(esc(s[last:]))
    return "".join(out)


def _render_footer(brief: dict, brand: dict) -> str:
    meta = brief.get("meta", {})
    left = " · ".join(esc(x) for x in (
        meta.get("confidential"),
        meta.get("source") or "Meltwater",
        meta.get("searchLabel"),
        meta.get("market"),
    ) if x)
    right = esc(brand.get("name") or meta.get("brandName") or "")
    return f'  <div class="foot"><span class="fl">{left}</span><span class="fr">{right}</span></div>'


# ── theme injection ────────────────────────────────────────────────────────
def _brand_tokens(brand: dict) -> str:
    theme = brand.get("theme", {})
    decls = [f"{var}:{theme[key]};" for key, var in _THEME_KEYS.items() if theme.get(key)]
    return f":root{{{''.join(decls)}}}" if decls else ""


# ── public entry point ─────────────────────────────────────────────────────
def render(brief: dict, brand: dict, template_path: Path = TEMPLATE_PATH) -> str:
    template = template_path.read_text(encoding="utf-8")

    body_parts = [
        _render_masthead(brief, brand),
        '  <div class="pad">',
        f'    <div class="exec"><span class="lab">Executive Summary</span><p>{esc(brief.get("execSummary"))}</p></div>',
        _render_sentiment(brief),
        "  </div>",
    ]
    for sec in brief.get("sections", []):
        body_parts.append('  <div class="pad">')
        body_parts.append(_render_section(sec))
        body_parts.append("  </div>")
    body_parts.append(_render_bottomline(brief))
    body_parts.append(_render_footer(brief, brand))
    body = "\n".join(p for p in body_parts if p)

    meta = brief.get("meta", {})
    title = f"{brand.get('name') or meta.get('brandName') or 'Media'} · Daily Brief — {meta.get('dateLong', '')}".strip(" —")

    return (
        template
        .replace("{{TITLE}}", esc(title))
        .replace("{{BRAND_TOKENS}}", _brand_tokens(brand))
        .replace("{{REPORT_BODY}}", body)
    )


def render_to_file(brief: dict, brand: dict, out_path: str,
                   template_path: Path = TEMPLATE_PATH) -> str:
    for w in validate(brief):
        print(f"WARN: {w}")
    out = render(brief, brand, template_path)
    Path(out_path).write_text(out, encoding="utf-8")
    print(f"OK: {len(out):,} bytes -> {out_path}")
    return out_path


# ── CLI: render a BRIEF json + brand json to HTML (handy for template work) ─
if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="Render a BRIEF json to a flat HTML brief.")
    ap.add_argument("brief", help="path to a BRIEF json file")
    ap.add_argument("--brand", default=os.environ.get("BRAND_CONFIG", "brands/example-brand.json"))
    ap.add_argument("--out", default="brief.html")
    args = ap.parse_args()
    brief = json.loads(Path(args.brief).read_text())
    brand = json.loads(Path(args.brand).read_text())
    render_to_file(brief, brand, args.out)
