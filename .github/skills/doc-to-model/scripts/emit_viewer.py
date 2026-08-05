#!/usr/bin/env python3
"""emit_viewer.py — projekce modelu do samostatné HTML stránky se stopou do zdroje.

Tři panely vedle sebe: **zdroj** (původní text), **model** (co se z něj vytáhlo)
a **výstupy** (co se z modelu vygenerovalo). Kliknutí na požadavek v prostředním
panelu odskočí na místo ve zdroji, ze kterého pochází.

Smysl: trasovatelnost se přestane vysvětlovat a začne ukazovat.

Stránka je offline a bez závislostí — jeden soubor, žádné CDN.

    python3 emit_viewer.py --model model.yaml --out out/prohlizec.html \\
        [--source zdroj.md] [--outputs out/]

Zdroj musí být text (.md/.txt). PDF si napřed vytáhni do textu.
"""
import argparse
import html
import json
import re
import sys
from pathlib import Path

import yaml

from pipeline_state import require, warn_if_missing
from sourcemap import anchor_sources

CONFIDENCE = {
    "explicit": ("doslova ve zdroji", "ok"),
    "derived": ("odvozeno", "warn"),
    "assumed": ("domyšleno", "bad"),
}
ARTIFACT_LABEL = {
    ".docx": "Word dokument",
    ".drawio": "Diagram (draw.io)",
    ".xlsx": "Excel",
    ".md": "Markdown",
    ".png": "Obrázek",
    ".svg": "Obrázek",
}


def load(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def by_id(items):
    return {it["id"]: it for it in (items or []) if "id" in it}


# ── HTML ──────────────────────────────────────────────────────────────────
CSS = """
:root{--bg:#fff;--fg:#1a1a1a;--muted:#666;--line:#e3e3e3;--card:#fafafa;
--ok:#2e7d32;--warn:#b26a00;--bad:#c62828;--accent:#1f497d;--hl:#fff3bf}
@media (prefers-color-scheme:dark){:root{--bg:#16181c;--fg:#e8e8e8;--muted:#9aa0a6;
--line:#2c3038;--card:#1e2127;--ok:#7cc47f;--warn:#e0a458;--bad:#ef6b6b;
--accent:#8ab4f8;--hl:#4a4224}}
*{box-sizing:border-box}
body{margin:0;font:15px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;
background:var(--bg);color:var(--fg)}
header{padding:18px 22px;border-bottom:1px solid var(--line)}
header h1{margin:0 0 4px;font-size:19px;color:var(--accent)}
header .meta{color:var(--muted);font-size:13px}
.stats{display:flex;gap:18px;flex-wrap:wrap;margin-top:10px;font-size:13px}
.stats b{font-size:17px;display:block;color:var(--accent)}
main{display:grid;grid-template-columns:1fr 1.15fr 0.85fr;gap:0;
height:calc(100vh - 118px)}
@media (max-width:1100px){main{grid-template-columns:1fr;height:auto}}
/* position:relative → offsetTop uvnitř panelu se počítá k panelu, ne k body */
section{overflow-y:auto;padding:16px 18px;border-right:1px solid var(--line);
position:relative}
section:last-child{border-right:none}
h2{font-size:13px;text-transform:uppercase;letter-spacing:.06em;color:var(--muted);
margin:0 0 12px;position:sticky;top:-16px;background:var(--bg);padding:6px 0;z-index:2}
h3{font-size:14px;margin:18px 0 8px}
.src{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:12.5px;
line-height:1.7;white-space:pre-wrap;word-break:break-word}
.src .ln{display:block;padding:0 4px;border-radius:3px}
.src .ln.hit{background:var(--hl)}
.card{border:1px solid var(--line);background:var(--card);border-radius:7px;
padding:10px 12px;margin-bottom:9px}
.card.click{cursor:pointer}
.card.click:hover{border-color:var(--accent)}
.card.active{border-color:var(--accent);box-shadow:0 0 0 2px color-mix(in srgb,var(--accent) 25%,transparent)}
.card h4{margin:0 0 5px;font-size:14px}
.card p{margin:5px 0;font-size:13.5px}
.chips{display:flex;gap:6px;flex-wrap:wrap;margin-top:7px}
.chip{font-size:11px;padding:2px 7px;border-radius:20px;border:1px solid var(--line);
color:var(--muted)}
.chip.ok{color:var(--ok);border-color:var(--ok)}
.chip.warn{color:var(--warn);border-color:var(--warn)}
.chip.bad{color:var(--bad);border-color:var(--bad)}
ul{margin:6px 0;padding-left:18px;font-size:13.5px}
li{margin:3px 0}
a{color:var(--accent)}
table{width:100%;border-collapse:collapse;font-size:13px;margin-top:6px}
th,td{text-align:left;padding:5px 7px;border-bottom:1px solid var(--line);
vertical-align:top}
th{color:var(--muted);font-weight:600;font-size:12px}
.empty{color:var(--muted);font-size:13px;font-style:italic}
.note{font-size:12px;color:var(--muted);margin-top:14px;padding-top:10px;
border-top:1px solid var(--line)}
.filter{display:flex;gap:6px;flex-wrap:wrap;margin:0 0 12px;position:sticky;top:26px;
background:var(--bg);padding:6px 0;z-index:2}
.filter button{font:inherit;font-size:12px;padding:3px 10px;border-radius:20px;
border:1px solid var(--line);background:transparent;color:var(--muted);cursor:pointer}
.filter button:hover{border-color:var(--accent)}
.filter button.on{border-color:var(--accent);color:var(--accent);font-weight:600}
.hidden{display:none}
"""

JS = """
const anchors = %(anchors)s;
function filtruj(mode, btn){
  document.querySelectorAll('.filter button').forEach(b=>b.classList.remove('on'));
  if(btn) btn.classList.add('on');
  // Skrývá se karta i její nadpis, jinak by ve výpisu zůstaly prázdné sekce.
  document.querySelectorAll('[data-kind]').forEach(el=>{
    const k = el.dataset.kind, c = el.dataset.conf || '';
    let show = true;
    if(mode === 'claims')   show = k === 'claim';
    if(mode === 'reqs')     show = k === 'req';
    if(mode === 'unsure')   show = c === 'assumed' || c === 'derived';
    el.classList.toggle('hidden', !show);
  });
  document.querySelectorAll('h3[data-section]').forEach(h=>{
    const vis = [...document.querySelectorAll(`[data-kind][data-section="${h.dataset.section}"]`)]
      .some(el=>!el.classList.contains('hidden'));
    h.classList.toggle('hidden', !vis);
  });
}

function jump(sid, el){
  document.querySelectorAll('.card.active').forEach(c=>c.classList.remove('active'));
  if(el) el.classList.add('active');
  document.querySelectorAll('.src .ln.hit').forEach(l=>l.classList.remove('hit'));
  const line = anchors[sid];
  if(line === null || line === undefined) return;
  for(let i=line;i<line+6;i++){
    const l = document.getElementById('l'+i);
    if(l) l.classList.add('hit');
  }
  // Posun počítáme sami a nastavujeme skokem. Dvě věci se cestou nepovedly:
  // scrollIntoView posouval dokument místo panelu, a plynulý scrollTo na dlouhé
  // vzdálenosti (12 000 px) občas neudělal nic. Přiřazení scrollTop je
  // spolehlivé a u takové vzdálenosti se skok čte lépe než klouzání.
  const t = document.getElementById('l'+line);
  if(!t) return;
  const pane = t.closest('section');
  if(pane) pane.scrollTop = Math.max(0, t.offsetTop - pane.clientHeight/2);
}
"""


def esc(x):
    return html.escape(str(x if x is not None else ""))


def onclick_attr(sid):
    """Atribut onclick pro kartu s odkazem do zdroje.

    Uvozovky musí být jako entity — jinak se atribut ukončí na prvním vnitřním
    uvozovkovém znaku a kliknutí tiše přestane fungovat.
    """
    if not sid:
        return ' class="card"'
    return f' class="card click" onclick="jump(&quot;{esc(sid)}&quot;, this)"'


def render_source(lines):
    if not lines:
        return '<p class="empty">Zdrojový text nebyl předán (parametr --source).</p>'
    out = ['<div class="src">']
    for i, line in enumerate(lines):
        out.append(f'<span class="ln" id="l{i}">{esc(line) or "&nbsp;"}</span>')
    out.append("</div>")
    return "".join(out)


def render_model(m, sources):
    actors = by_id(m.get("actors"))
    claims = by_id(m.get("claims"))
    out = []

    if m.get("context"):
        out.append("<h3>Kontext</h3>")
        out.append(f'<div class="card"><p>{esc(str(m["context"]).strip())}</p></div>')

    if m.get("actors"):
        out.append("<h3>Aktéři</h3>")
        for a in m["actors"]:
            role = f' — {esc(a.get("role"))}' if a.get("role") else ""
            out.append(
                f'<div class="card"><h4>{esc(a.get("name"))}</h4>'
                f'<p>{esc(a.get("id"))}{role}</p></div>'
            )

    if m.get("claims"):
        out.append(f'<h3 data-section="claim">Tvrzení ({len(m["claims"])})</h3>')
        for c in m["claims"]:
            chips = []
            if c.get("claim_type"):
                chips.append(f'<span class="chip">{esc(c["claim_type"])}</span>')
            conf = c.get("confidence")
            if conf:
                label, cls = CONFIDENCE.get(conf, (conf, ""))
                chips.append(f'<span class="chip {cls}">{esc(label)}</span>')
            src = sources.get(c.get("source"), {})
            if src:
                loc = f' · {esc(src.get("locator"))}' if src.get("locator") else ""
                chips.append(f'<span class="chip">{esc(src.get("title"))}{loc}</span>')

            basis = (f'<p><strong>Opora:</strong> {esc(c["basis"])}</p>'
                     if c.get("basis")
                     else '<p class="empty">Zdroj neuvádí, o co se tvrzení opírá.</p>')
            scope = f'<p><em>Rozsah platnosti: {esc(c["scope"])}</em></p>' if c.get("scope") else ""

            out.append(
                f"<div{onclick_attr(c.get('source'))}"
                f' data-kind="claim" data-section="claim" data-conf="{esc(conf or "")}">'
                f"<h4>{esc(c.get('id'))} — {esc(c.get('title'))}</h4>"
                f"<p>{esc(str(c.get('description', '')).strip())}</p>"
                f'{basis}{scope}<div class="chips">{"".join(chips)}</div></div>'
            )

    if m.get("requirements"):
        out.append(f'<h3 data-section="req">Požadavky ({len(m["requirements"])})</h3>')
        for r in m["requirements"]:
            chips = []
            if r.get("priority"):
                chips.append(f'<span class="chip">{esc(r["priority"])}</span>')
            conf = r.get("confidence")
            if conf:
                label, cls = CONFIDENCE.get(conf, (conf, ""))
                chips.append(f'<span class="chip {cls}">{esc(label)}</span>')
            if r.get("actor"):
                who = actors.get(r["actor"], {}).get("name", r["actor"])
                chips.append(f'<span class="chip">{esc(who)}</span>')
            src = sources.get(r.get("source"), {})
            if src:
                loc = f' · {esc(src.get("locator"))}' if src.get("locator") else ""
                chips.append(f'<span class="chip">{esc(src.get("title"))}{loc}</span>')
            for j in r.get("justified_by") or []:
                title = claims.get(j, {}).get("title", j)
                chips.append(f'<span class="chip">plyne z: {esc(title)}</span>')

            acc = ""
            if r.get("acceptance"):
                items = "".join(f"<li>{esc(a)}</li>" for a in r["acceptance"])
                acc = f"<p><strong>Akceptace:</strong></p><ul>{items}</ul>"
            else:
                acc = '<p class="empty">Zdroj neuvádí akceptační kritérium.</p>'

            sid = r.get("source")
            click = onclick_attr(sid)
            out.append(
                f"<div{click}"
                f' data-kind="req" data-section="req" data-conf="{esc(conf or "")}">'
                f"<h4>{esc(r.get('id'))} — {esc(r.get('title'))}</h4>"
                f"<p>{esc(str(r.get('description', '')).strip())}</p>"
                f'{acc}<div class="chips">{"".join(chips)}</div></div>'
            )

    if m.get("quality_requirements"):
        out.append(f'<h3>Nefunkční požadavky ({len(m["quality_requirements"])})</h3>')
        for q in m["quality_requirements"]:
            sid = q.get("source")
            click = onclick_attr(sid)
            out.append(
                f"<div{click}><h4>{esc(q.get('id'))} · {esc(q.get('category'))}</h4>"
                f"<p>{esc(str(q.get('requirement', '')).strip())}</p></div>"
            )

    if m.get("entities"):
        out.append(f'<h3>Datový model ({len(m["entities"])})</h3>')
        for e in m["entities"]:
            rows = "".join(
                f"<tr><td><code>{esc(f.get('name'))}</code></td><td>{esc(f.get('type'))}</td>"
                f"<td>{'ano' if f.get('required_field') else 'ne'}</td></tr>"
                for f in e.get("fields") or []
            )
            table = (
                f"<table><tr><th>Pole</th><th>Typ</th><th>Povinné</th></tr>{rows}</table>"
                if rows else ""
            )
            out.append(
                f'<div class="card"><h4>{esc(e.get("name"))}</h4>'
                f'<p>{esc(e.get("description"))}</p>{table}</div>'
            )

    proc = m.get("process") or {}
    if proc.get("steps"):
        out.append(f'<h3>Proces — {esc(proc.get("name"))}</h3>')
        rows = "".join(
            f"<tr><td><code>{esc(s.get('id'))}</code></td><td>{esc(s.get('type'))}</td>"
            f"<td>{esc(s.get('label'))}</td></tr>"
            for s in proc["steps"]
        )
        out.append(f'<div class="card"><table>{rows}</table></div>')

    if m.get("risks"):
        out.append(f'<h3>Rizika ({len(m["risks"])})</h3>')
        for r in m["risks"]:
            mit = f'<p><em>Opatření:</em> {esc(r.get("mitigation"))}</p>' if r.get("mitigation") else ""
            out.append(
                f'<div class="card"><h4>{esc(r.get("id"))}</h4>'
                f'<p>{esc(r.get("description"))}</p>{mit}</div>'
            )

    return "".join(out)


def render_outputs(m, out_dir: Path, viewer_path: Path):
    parts = []

    if out_dir and out_dir.is_dir():
        files = sorted(
            p for p in out_dir.iterdir()
            if p.is_file() and p != viewer_path and not p.name.startswith(".")
        )
        if files:
            parts.append("<h3>Vygenerované artefakty</h3>")
            for p in files:
                label = ARTIFACT_LABEL.get(p.suffix.lower(), p.suffix.lstrip(".").upper())
                size = f"{p.stat().st_size / 1024:.0f} kB"
                rel = p.name
                parts.append(
                    f'<div class="card"><h4><a href="{esc(rel)}">{esc(p.name)}</a></h4>'
                    f'<p>{esc(label)} · {size}</p></div>'
                )

    if m.get("open_questions"):
        parts.append(f'<h3>Otevřené otázky ({len(m["open_questions"])})</h3>')
        items = "".join(f"<li>{esc(q)}</li>" for q in m["open_questions"])
        parts.append(f'<div class="card"><ul>{items}</ul></div>')

    if m.get("regulations"):
        parts.append("<h3>Předpisy</h3>")
        items = "".join(f"<li>{esc(x)}</li>" for x in m["regulations"])
        parts.append(f'<div class="card"><ul>{items}</ul></div>')

    return "".join(parts) or '<p class="empty">Zatím nic.</p>'


def build_html(m, lines, anchors, out_dir, viewer_path, anchored, total_src):
    sources = by_id(m.get("sources"))
    reqs = len(m.get("requirements") or [])
    claims_n = len(m.get("claims") or [])
    without_acc = sum(1 for r in (m.get("requirements") or []) if not r.get("acceptance"))
    steps = len((m.get("process") or {}).get("steps") or [])

    # Statistiky ukazují jen to, co model opravdu obsahuje — u analýzy nemá smysl
    # hlásit nulu požadavků a u specifikace nulu tvrzení.
    stats = []
    if claims_n:
        stats.append(("Tvrzení", claims_n))
    if reqs:
        stats += [("Požadavky", reqs), ("Bez akceptace", without_acc)]
    stats += [
        ("Kroky procesu", steps),
        ("Zdrojová místa", len(sources)),
        ("Řádků zdroje", len(lines)),
    ]
    stats = [(k, v) for k, v in stats if v or k in ("Bez akceptace",)]
    stats_html = "".join(
        f"<div><b>{v}</b>{esc(k)}</div>" for k, v in stats
    )

    # Filtr má smysl jen tam, kde je z čeho vybírat.
    filtr = ""
    if claims_n and reqs:
        filtr = (
            '<div class="filter">'
            '<button class="on" onclick="filtruj(&quot;all&quot;, this)">Vše</button>'
            '<button onclick="filtruj(&quot;claims&quot;, this)">Jen tvrzení</button>'
            '<button onclick="filtruj(&quot;reqs&quot;, this)">Jen požadavky</button>'
            '<button onclick="filtruj(&quot;unsure&quot;, this)">Neověřené</button>'
            "</div>"
        )
    elif claims_n or reqs:
        filtr = (
            '<div class="filter">'
            '<button class="on" onclick="filtruj(&quot;all&quot;, this)">Vše</button>'
            '<button onclick="filtruj(&quot;unsure&quot;, this)">Neověřené</button>'
            "</div>"
        )

    note = (
        f"Odkazy do zdroje se dohledávají podle pole <code>locator</code>. "
        f"Zakotveno {anchored} z {total_src} zdrojových míst — u zbytku kliknutí "
        f"jen označí požadavek."
    )

    return f"""<!doctype html>
<html lang="cs"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(m.get('title', 'Model'))}</title>
<style>{CSS}</style></head><body>
<header>
  <h1>{esc(m.get('title', 'Model'))}</h1>
  <div class="meta">{esc(m.get('id'))} · v{esc(m.get('version'))} · {esc(m.get('status'))}
   · zdroj: {esc(m.get('source_document'))}</div>
  <div class="stats">{stats_html}</div>
</header>
<main>
  <section><h2>Zdroj</h2>{render_source(lines)}</section>
  <section><h2>Model</h2>{filtr}{render_model(m, sources)}
    <p class="note">{note}</p></section>
  <section><h2>Výstupy</h2>{render_outputs(m, out_dir, viewer_path)}</section>
</main>
<script>{JS % {'anchors': json.dumps(anchors)}}</script>
</body></html>
"""


def main():
    ap = argparse.ArgumentParser(description="Emit HTML prohlížeč modelu se stopou do zdroje.")
    ap.add_argument("--model", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--source", type=Path, help="Zdrojový text (.md/.txt).")
    ap.add_argument("--outputs", type=Path, help="Adresář s vygenerovanými artefakty.")
    args = ap.parse_args()

    require(args.model, ["validate"], "emit")
    warn_if_missing(args.model, "ground-check",
                    "prohlížeč může ukazovat tvrzení bez opory ve zdroji")
    warn_if_missing(args.model, "coverage-check",
                    "prohlížeč nedá poznat, kolik zdroje se do modelu nedostalo")

    m = load(args.model)
    sources = by_id(m.get("sources"))

    lines = []
    if args.source:
        if args.source.suffix.lower() == ".pdf":
            sys.exit("[CHYBA] --source čeká text. PDF si napřed vytáhni do .txt.")
        if not args.source.exists():
            sys.exit(f"[CHYBA] Zdroj nenalezen: {args.source}")
        lines = args.source.read_text(encoding="utf-8").splitlines()

    anchors = anchor_sources(lines, sources) if lines else {k: None for k in sources}
    anchored = sum(1 for v in anchors.values() if v is not None)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        build_html(m, lines, anchors, args.outputs, args.out.resolve(), anchored, len(sources)),
        encoding="utf-8",
    )
    if lines:
        print(f"[OK] prohlížeč: {args.out} (zakotveno {anchored}/{len(sources)} zdrojů)")
        # Prohlížeč se dá spustit i mimo build.sh, kde bránu zakotvenosti drží
        # ground_check. Bez tohohle řádku by vznikla stránka, kde odskok nikam
        # nevede, a v logu by stálo jen [OK].
        if sources and not anchored:
            print("  [POZOR] nezakotvil se ani jeden zdroj — odskok z výroku do textu "
                  "nebude fungovat nikde.")
            print("          `locator` musí být doslovný řetězec z dokumentu, "
                  "ne skládaná cesta „Rodič / Dítě\".")
    else:
        print(f"[OK] prohlížeč: {args.out} (bez zdrojového textu)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
