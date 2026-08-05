#!/usr/bin/env python3
"""emit_word.py — deterministický emitor: instance analytical-doc → .docx

Čte jednu instanci strukturované pravdy a vygeneruje strukturovaný Word dokument.
Stejný vstup = stejný výstup, žádné generování textu.

Každá sekce je volitelná — emitor vypíše jen to, co v modelu je.

    python3 emit_word.py --model model.yaml --out out/dokument.docx
"""
import argparse
import sys
from pathlib import Path

import yaml

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Pt, RGBColor

from pipeline_state import require, warn_if_missing

BRAND = RGBColor(0x1F, 0x49, 0x7D)
PRIORITY_ORDER = {"MUST": 0, "SHOULD": 1, "COULD": 2, "WONT": 3}
CONFIDENCE_LABEL = {
    "explicit": "doslova ve zdroji",
    "derived": "odvozeno",
    "assumed": "doplněno — ověřit",
}


def load(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def index_by_id(items):
    return {it["id"]: it for it in (items or []) if "id" in it}


def kv_table(doc, rows):
    t = doc.add_table(rows=0, cols=2)
    t.style = "Light Grid Accent 1"
    for k, v in rows:
        if v in (None, "", []):
            continue
        cells = t.add_row().cells
        cells[0].text = str(k)
        cells[1].text = "\n".join(v) if isinstance(v, list) else str(v)
        for p in cells[0].paragraphs:
            for run in p.runs:
                run.bold = True
    return t


def header_table(doc, headers):
    t = doc.add_table(rows=1, cols=len(headers))
    t.style = "Light Grid Accent 1"
    for i, h in enumerate(headers):
        cell = t.rows[0].cells[i]
        cell.text = h
        for p in cell.paragraphs:
            for run in p.runs:
                run.bold = True
    return t


def source_label(src_id, sources):
    src = sources.get(src_id)
    if not src:
        return src_id or ""
    parts = [src.get("title", src_id)]
    if src.get("locator"):
        parts.append(src["locator"])
    return ", ".join(parts)


def build(m: dict) -> Document:
    doc = Document()
    normal = doc.styles["Normal"]
    normal.font.name = "Calibri"
    normal.font.size = Pt(10.5)

    sources = index_by_id(m.get("sources"))
    actors = index_by_id(m.get("actors"))

    title = doc.add_heading(m.get("title", "Bez názvu"), level=0)
    for run in title.runs:
        run.font.color.rgb = BRAND

    if m.get("subtitle"):
        sub = doc.add_paragraph(m["subtitle"])
        sub.alignment = WD_ALIGN_PARAGRAPH.LEFT
        if sub.runs:
            sub.runs[0].italic = True

    kv_table(doc, [
        ("ID", m.get("id")),
        ("Verze", m.get("version")),
        ("Stav", m.get("status")),
        ("Autor", m.get("author")),
        ("Datum", m.get("date")),
        ("Zdrojový dokument", m.get("source_document")),
        ("Předpisy", m.get("regulations")),
    ])
    doc.add_paragraph()

    n = 0

    if m.get("context"):
        n += 1
        doc.add_heading(f"{n}. Kontext", level=1)
        doc.add_paragraph(str(m["context"]).strip())

    if m.get("actors"):
        n += 1
        doc.add_heading(f"{n}. Aktéři", level=1)
        t = header_table(doc, ["ID", "Aktér", "Role"])
        for a in m["actors"]:
            c = t.add_row().cells
            c[0].text = a.get("id", "")
            c[1].text = a.get("name", "")
            c[2].text = a.get("role", "")

    if m.get("scope_in") or m.get("scope_out"):
        n += 1
        doc.add_heading(f"{n}. Rozsah", level=1)
        if m.get("scope_in"):
            doc.add_heading("V rozsahu", level=2)
            for item in m["scope_in"]:
                doc.add_paragraph(item, style="List Bullet")
        if m.get("scope_out"):
            doc.add_heading("Mimo rozsah", level=2)
            for item in m["scope_out"]:
                doc.add_paragraph(item, style="List Bullet")

    if m.get("claims"):
        n += 1
        doc.add_heading(f"{n}. Tvrzení", level=1)
        for c in m["claims"]:
            head = f"{c.get('id', '')} — {c.get('title', '')}"
            if c.get("claim_type"):
                head += f"  [{c['claim_type']}]"
            doc.add_heading(head, level=2)
            if c.get("description"):
                doc.add_paragraph(str(c["description"]).strip())
            if c.get("basis"):
                p = doc.add_paragraph(f"Opora: {c['basis']}")
                if p.runs:
                    p.runs[0].italic = True
            meta_bits = []
            if c.get("scope"):
                meta_bits.append(f"Rozsah platnosti: {c['scope']}")
            if c.get("source"):
                meta_bits.append(f"Zdroj: {source_label(c['source'], sources)}")
            if c.get("confidence"):
                meta_bits.append(CONFIDENCE_LABEL.get(c["confidence"], c["confidence"]))
            if meta_bits:
                p = doc.add_paragraph(" · ".join(meta_bits))
                if p.runs:
                    p.runs[0].italic = True

    if m.get("requirements"):
        n += 1
        doc.add_heading(f"{n}. Funkční požadavky", level=1)
        reqs = sorted(
            m["requirements"],
            key=lambda r: (PRIORITY_ORDER.get(r.get("priority"), 9), r.get("id", "")),
        )
        for r in reqs:
            head = f"{r.get('id', '')} — {r.get('title', '')}"
            if r.get("priority"):
                head += f"  [{r['priority']}]"
            doc.add_heading(head, level=2)
            if r.get("description"):
                doc.add_paragraph(str(r["description"]).strip())
            if r.get("acceptance"):
                p = doc.add_paragraph("Akceptační kritéria:")
                p.runs[0].bold = True
                for ac in r["acceptance"]:
                    doc.add_paragraph(ac, style="List Bullet")
            if r.get("justified_by"):
                claims_by_id = index_by_id(m.get("claims"))
                duvody = "; ".join(
                    f"{j} — {claims_by_id.get(j, {}).get('title', '?')}"
                    for j in r["justified_by"]
                )
                p = doc.add_paragraph(f"Plyne z: {duvody}")
                if p.runs:
                    p.runs[0].italic = True
            meta_bits = []
            if r.get("actor"):
                who = actors.get(r["actor"], {}).get("name", r["actor"])
                meta_bits.append(f"Odpovídá: {who}")
            if r.get("source"):
                meta_bits.append(f"Zdroj: {source_label(r['source'], sources)}")
            if r.get("confidence"):
                meta_bits.append(CONFIDENCE_LABEL.get(r["confidence"], r["confidence"]))
            if meta_bits:
                p = doc.add_paragraph(" · ".join(meta_bits))
                if p.runs:
                    p.runs[0].italic = True

    if m.get("quality_requirements"):
        n += 1
        doc.add_heading(f"{n}. Nefunkční požadavky", level=1)
        t = header_table(doc, ["ID", "Kategorie", "Požadavek", "Zdroj"])
        for q in m["quality_requirements"]:
            c = t.add_row().cells
            c[0].text = q.get("id", "")
            c[1].text = q.get("category", "")
            c[2].text = str(q.get("requirement", "")).strip()
            c[3].text = source_label(q.get("source"), sources)

    if m.get("entities"):
        n += 1
        doc.add_heading(f"{n}. Datový model", level=1)
        for e in m["entities"]:
            doc.add_heading(f"{e.get('name', e.get('id', ''))}", level=2)
            if e.get("description"):
                doc.add_paragraph(e["description"])
            if e.get("fields"):
                t = header_table(doc, ["Pole", "Typ", "Povinné", "Poznámka"])
                for f in e["fields"]:
                    c = t.add_row().cells
                    c[0].text = f.get("name", "")
                    c[1].text = f.get("type", "")
                    c[2].text = "Ano" if f.get("required_field") else "Ne"
                    c[3].text = f.get("note", "")

    if m.get("process"):
        n += 1
        doc.add_heading(f"{n}. Procesní tok", level=1)
        proc = m["process"]
        doc.add_paragraph(proc.get("name", ""))
        t = header_table(doc, ["Krok", "Typ", "Popis", "Aktér", "Pokračuje"])
        for s in proc.get("steps", []):
            c = t.add_row().cells
            c[0].text = s.get("id", "")
            c[1].text = s.get("type", "")
            c[2].text = s.get("label", "")
            c[3].text = actors.get(s.get("actor"), {}).get("name", s.get("actor", "") or "")
            if s.get("branches"):
                c[4].text = "; ".join(
                    f"{b.get('label')} → {b.get('target')}" for b in s["branches"]
                )
            else:
                c[4].text = s.get("next", "") or ""
        p = doc.add_paragraph(
            "Diagram téhož procesu se generuje ze stejného modelu (emit_drawio.py)."
        )
        if p.runs:
            p.runs[0].italic = True

    if m.get("risks"):
        n += 1
        doc.add_heading(f"{n}. Rizika", level=1)
        t = header_table(doc, ["ID", "Riziko", "Opatření"])
        for r in m["risks"]:
            c = t.add_row().cells
            c[0].text = r.get("id", "")
            c[1].text = r.get("description", "")
            c[2].text = r.get("mitigation", "") or ""

    if m.get("open_questions"):
        n += 1
        doc.add_heading(f"{n}. Otevřené otázky", level=1)
        for q in m["open_questions"]:
            doc.add_paragraph(q, style="List Bullet")

    if sources:
        n += 1
        doc.add_heading(f"{n}. Zdroje", level=1)
        t = header_table(doc, ["ID", "Zdroj", "Místo"])
        for sid, s in sources.items():
            c = t.add_row().cells
            c[0].text = sid
            c[1].text = s.get("title", "")
            c[2].text = s.get("locator", "") or s.get("url", "") or ""

    footer = doc.sections[0].footer
    footer.paragraphs[0].text = (
        f"{m.get('id', '')} v{m.get('version', '')} · generováno deterministicky z modelu"
    )
    return doc


def main():
    ap = argparse.ArgumentParser(description="Emit .docx z instance analytical-doc.")
    ap.add_argument("--model", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args()

    require(args.model, ["validate"], "emit")
    warn_if_missing(args.model, "ground-check",
                    "výstup může nést tvrzení bez opory ve zdroji")

    m = load(args.model)
    doc = build(m)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    doc.save(args.out)

    # Počty, ne jen cesta. Word z jednoho požadavku vypadal v logu stejně jako
    # ze dvou set — a tenhle řádek je často jediné, co člověk z běhu přečte.
    reqs = len(m.get("requirements") or []) + len(m.get("quality_requirements") or [])
    claims = len(m.get("claims") or [])
    steps = len((m.get("process") or {}).get("steps") or [])
    print(f"[OK] Word: {args.out} "
          f"({reqs} požadavků · {claims} tvrzení · {steps} kroků procesu)")

    if not reqs and not claims:
        print("  [POZOR] dokument nenese žádný požadavek ani tvrzení — "
              "vznikl formálně správný, ale prázdný výstup.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
