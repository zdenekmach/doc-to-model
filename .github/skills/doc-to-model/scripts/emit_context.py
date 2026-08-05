#!/usr/bin/env python3
"""emit_context.py — projekce modelu do kontextu pro AI + report děr.

Dva výstupy z jednoho modelu:

* **kontext** (`--out`) — kompaktní markdown, který se dá vložit do promptu nebo
  uložit jako projektový kontext. Obsahuje jen fakta z modelu, žádnou prózu navíc.
* **díry** (`--gaps`) — kde model nedrží: prvky bez zdroje, prvky označené jako
  `assumed`, požadavky bez akceptačního kritéria, osamocené kroky procesu.

Report děr je ta část, kvůli které se to vyplatí: říká, co se ze zdroje nedalo
vyčíst a musí doplnit člověk.

    python3 emit_context.py --model model.yaml --out out/kontext.md [--gaps out/diry.md]
"""
import argparse
import sys
from pathlib import Path

import yaml

from pipeline_state import require, warn_if_missing


def load(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def by_id(items):
    return {it["id"]: it for it in (items or []) if "id" in it}


# Sekce, které umí emitor vypsat po svém. Cokoli dalšího v instanci se vypíše
# obecně — vlastní schéma (viz /data-metamodel) tak nepřijde o obsah jen proto,
# že o něm tenhle skript neví.
KNOWN_SLOTS = {
    "id", "title", "subtitle", "version", "status", "author", "date",
    "source_document", "regulations", "context", "sources", "actors",
    "scope_in", "scope_out", "claims", "requirements", "quality_requirements",
    "entities", "process", "risks", "open_questions",
}


def render_unknown(m: dict):
    """Kolekce, které schéma přidalo a tenhle emitor je nezná."""
    out = []
    for slot, value in m.items():
        if slot in KNOWN_SLOTS or value in (None, "", [], {}):
            continue
        out.append(f"\n## {slot}\n")
        if isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    label = item.get("title") or item.get("name") or item.get("id") or "—"
                    detail = item.get("description") or ""
                    out.append(f"- **{label}** {detail}".rstrip())
                else:
                    out.append(f"- {item}")
        elif isinstance(value, dict):
            for k, v in value.items():
                out.append(f"- {k}: {v}")
        else:
            out.append(str(value))
    return out


def render_context(m: dict) -> str:
    actors = by_id(m.get("actors"))
    sources = by_id(m.get("sources"))
    claims_by_id = by_id(m.get("claims"))
    out = []

    out.append(f"# {m.get('title', 'Analytický dokument')}")
    ident = [b for b in [m.get("id"), m.get("version") and f"v{m['version']}", m.get("status")] if b]
    if ident:
        out.append(" · ".join(str(b) for b in ident))
    if m.get("source_document"):
        out.append(f"\nZdroj: {m['source_document']}")
    if m.get("regulations"):
        out.append("\nPředpisy: " + "; ".join(m["regulations"]))

    if m.get("context"):
        out.append("\n## Kontext\n")
        out.append(str(m["context"]).strip())

    if actors:
        out.append("\n## Aktéři\n")
        for a in actors.values():
            role = f" — {a['role']}" if a.get("role") else ""
            out.append(f"- **{a.get('name')}** (`{a['id']}`){role}")

    if m.get("scope_in") or m.get("scope_out"):
        out.append("\n## Rozsah\n")
        for item in m.get("scope_in") or []:
            out.append(f"- v rozsahu: {item}")
        for item in m.get("scope_out") or []:
            out.append(f"- mimo rozsah: {item}")

    if m.get("claims"):
        out.append("\n## Tvrzení\n")
        for c in m["claims"]:
            kind = f" [{c['claim_type']}]" if c.get("claim_type") else ""
            out.append(f"### {c.get('id')} — {c.get('title')}{kind}")
            if c.get("description"):
                out.append(str(c["description"]).strip())
            if c.get("basis"):
                out.append(f"- opora: {c['basis']}")
            if c.get("scope"):
                out.append(f"- rozsah platnosti: {c['scope']}")
            if c.get("source"):
                src = sources.get(c["source"], {})
                loc = f", {src['locator']}" if src.get("locator") else ""
                out.append(f"- zdroj: {src.get('title', c['source'])}{loc}")
            if c.get("confidence") and c["confidence"] != "explicit":
                out.append(f"- jistota: {c['confidence']}")
            out.append("")

    if m.get("requirements"):
        out.append("\n## Požadavky\n")
        for r in m["requirements"]:
            prio = f" [{r['priority']}]" if r.get("priority") else ""
            out.append(f"### {r.get('id')} — {r.get('title')}{prio}")
            if r.get("description"):
                out.append(str(r["description"]).strip())
            for ac in r.get("acceptance") or []:
                out.append(f"- akceptace: {ac}")
            if r.get("source"):
                src = sources.get(r["source"], {})
                loc = f", {src['locator']}" if src.get("locator") else ""
                out.append(f"- zdroj: {src.get('title', r['source'])}{loc}")
            for j in r.get("justified_by") or []:
                claim = claims_by_id.get(j, {})
                out.append(f"- plyne z: {j} — {claim.get('title', '?')}")
            if r.get("confidence") and r["confidence"] != "explicit":
                out.append(f"- jistota: {r['confidence']}")
            out.append("")

    if m.get("quality_requirements"):
        out.append("\n## Nefunkční požadavky\n")
        for q in m["quality_requirements"]:
            out.append(f"- **{q.get('id')}** ({q.get('category')}): {q.get('requirement')}")

    if m.get("entities"):
        out.append("\n## Datový model\n")
        for e in m["entities"]:
            out.append(f"### {e.get('name')}")
            if e.get("description"):
                out.append(e["description"])
            for f in e.get("fields") or []:
                req = "povinné" if f.get("required_field") else "volitelné"
                note = f" — {f['note']}" if f.get("note") else ""
                out.append(f"- `{f.get('name')}` ({f.get('type', '?')}, {req}){note}")
            out.append("")

    proc = m.get("process") or {}
    if proc.get("steps"):
        out.append(f"\n## Proces: {proc.get('name', '')}\n")
        for s in proc["steps"]:
            who = actors.get(s.get("actor"), {}).get("name")
            who = f" [{who}]" if who else ""
            if s.get("branches"):
                nxt = "; ".join(f"{b.get('label')} → {b.get('target')}" for b in s["branches"])
            else:
                nxt = s.get("next") or "—"
            out.append(f"- `{s.get('id')}` ({s.get('type')}){who}: {s.get('label')} → {nxt}")

    if m.get("risks"):
        out.append("\n## Rizika\n")
        for r in m["risks"]:
            mit = f" Opatření: {r['mitigation']}" if r.get("mitigation") else ""
            out.append(f"- **{r.get('id')}**: {r.get('description')}{mit}")

    if m.get("open_questions"):
        out.append("\n## Otevřené otázky\n")
        for q in m["open_questions"]:
            out.append(f"- {q}")

    out += render_unknown(m)

    return "\n".join(out) + "\n"


def collect_gaps(m: dict):
    """Kde model nedrží.

    Pravidla se větví podle typu výroku, ne podle žánru dokumentu. Požadavek bez
    akceptačního kritéria je nález; tvrzení žádné mít nemá. Kdyby se pravidla
    nevětvila, report u analýzy by byl ze dvou třetin šum a nikdo by ho nečetl.
    """
    gaps = []
    step_ids = {s.get("id") for s in (m.get("process") or {}).get("steps", [])}

    for c in m.get("claims") or []:
        cid = c.get("id", "?")
        if not c.get("source"):
            gaps.append(("tvrzení bez zdroje", cid, "nelze dohledat, odkud pochází"))
        if not c.get("basis"):
            gaps.append(("tvrzení bez opory", cid, "zdroj neuvádí, o co se tvrzení opírá"))
        if c.get("confidence") == "assumed":
            gaps.append(("domyšlené tvrzení", cid, "ve zdroji chybí — ověřit s autorem"))
        elif c.get("confidence") == "derived":
            gaps.append(("odvozené tvrzení", cid, "neplyne z jednoho místa zdroje — ověřit výklad"))
        if c.get("claim_type") == "predikce" and c.get("confidence") == "explicit":
            gaps.append(("predikce vydávaná za doložený fakt", cid,
                         "budoucnost nemůže být ve zdroji doslova"))

    # Pravidlo o odůvodnění se zapne jen tam, kde ho někdo skutečně používá.
    # Kdyby platilo vždycky, zaplavilo by report u modelů, kde vazba požadavek →
    # tvrzení nedává smysl, a svádělo by k vymýšlení odůvodnění pro forma.
    justification_used = any(r.get("justified_by") for r in (m.get("requirements") or []))

    for r in m.get("requirements") or []:
        rid = r.get("id", "?")
        if justification_used and not r.get("justified_by"):
            gaps.append(("požadavek bez odůvodnění", rid,
                         "neukazuje na tvrzení, ze kterého plyne"))
        if not r.get("source"):
            gaps.append(("požadavek bez zdroje", rid, "nelze dohledat, odkud plyne"))
        if not r.get("acceptance"):
            gaps.append(("požadavek bez akceptace", rid, "není podle čeho zkontrolovat"))
        if r.get("confidence") == "assumed":
            gaps.append(("domyšlený požadavek", rid, "ve zdroji chybí — ověřit s autorem"))
        elif r.get("confidence") == "derived":
            gaps.append(("odvozený požadavek", rid, "neplyne z jednoho místa zdroje — ověřit výklad"))

    for q in m.get("quality_requirements") or []:
        if not q.get("source"):
            gaps.append(("nefunkční požadavek bez zdroje", q.get("id", "?"), ""))
        if q.get("confidence") == "assumed":
            gaps.append(("domyšlený nefunkční požadavek", q.get("id", "?"), "ověřit"))

    referenced = set()
    for s in (m.get("process") or {}).get("steps", []):
        if s.get("next"):
            referenced.add(s["next"])
        for b in s.get("branches") or []:
            if b.get("target"):
                referenced.add(b["target"])
    for s in (m.get("process") or {}).get("steps", []):
        sid = s.get("id")
        if s.get("type") not in ("start",) and sid not in referenced:
            gaps.append(("nedosažitelný krok", sid, "žádný krok na něj neukazuje"))
        if s.get("type") not in ("end",) and not s.get("next") and not s.get("branches"):
            gaps.append(("slepý krok", sid, "nemá pokračování"))

    if not m.get("open_questions"):
        gaps.append(("žádné otevřené otázky", "—", "podezřelé u reálného zdroje"))
    # Chybějící proces je nález jen tam, kde dokument něco požaduje. Analýza
    # ani výklad předpisu sled kroků popisovat nemusí — hlásit to jako díru
    # by byl šum, ne zjištění.
    if not step_ids and (m.get("requirements") or []):
        gaps.append(("chybí proces", "—", "specifikace nepopisuje sled kroků"))

    return gaps


def render_gaps(m: dict, gaps) -> str:
    out = [f"# Kde model nedrží — {m.get('title', '')}", ""]
    if not gaps:
        out.append("Žádné díry nenalezeny.")
        return "\n".join(out) + "\n"
    out.append(f"Nalezeno **{len(gaps)}** míst k doplnění.")
    out.append("")
    out.append("| Druh | Prvek | Poznámka |")
    out.append("|------|-------|----------|")
    for kind, elem, note in gaps:
        out.append(f"| {kind} | `{elem}` | {note} |")
    return "\n".join(out) + "\n"


def main():
    ap = argparse.ArgumentParser(description="Projekce modelu do AI kontextu a reportu děr.")
    ap.add_argument("--model", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--gaps", type=Path)
    args = ap.parse_args()

    require(args.model, ["validate"], "emit")
    warn_if_missing(args.model, "ground-check",
                    "výstup může nést tvrzení bez opory ve zdroji")

    m = load(args.model)

    reqs = len(m.get("requirements") or []) + len(m.get("quality_requirements") or [])
    claims = len(m.get("claims") or [])

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(render_context(m), encoding="utf-8")
    print(f"[OK] kontext: {args.out} ({reqs} požadavků · {claims} tvrzení)")

    if args.gaps:
        gaps = collect_gaps(m)
        args.gaps.parent.mkdir(parents=True, exist_ok=True)
        args.gaps.write_text(render_gaps(m, gaps), encoding="utf-8")
        print(f"[OK] díry: {args.gaps} ({len(gaps)} nálezů)")

        # Prázdný report děr je podezřelý, ne pochvalný. Reálné dokumenty díry
        # mají; nula obvykle znamená mělkou extrakci, ne dokonalý zdroj. Stálo
        # to v SKILL.md jako varování, ale ne tam, kde to člověk čte — v běhu.
        if not gaps and (reqs or claims):
            print("  [POZOR] report děr nenašel nic. U reálného dokumentu to spíš "
                  "znamená mělkou extrakci než bezchybný zdroj —")
            print("          projdi, jestli má každý požadavek akceptační kritérium "
                  "a jestli model pokrývá celý dokument.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
