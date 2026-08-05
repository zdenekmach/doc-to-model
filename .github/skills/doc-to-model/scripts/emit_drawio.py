#!/usr/bin/env python3
"""emit_drawio.py — deterministický emitor: instance analytical-doc → .drawio

Z modelu (process.steps) vygeneruje editovatelný diagram pro draw.io / diagrams.net.
Stejný vstup = stejný výstup.

Volitelně `--swimlanes` rozloží kroky do sloupců podle aktéra.

    python3 emit_drawio.py --model model.yaml --out out/process.drawio [--swimlanes]
"""
import argparse
import sys
from pathlib import Path
from xml.sax.saxutils import escape

import yaml

from pipeline_state import require, warn_if_missing

MAIN_X = 280
SIDE_X = 600
LANE_W = 260
TOP_Y = 60
DY = 120

STYLE = {
    "start": "rounded=1;whiteSpace=wrap;html=1;fillColor=#d5e8d4;strokeColor=#82b366;",
    "end": "rounded=1;whiteSpace=wrap;html=1;fillColor=#d5e8d4;strokeColor=#82b366;",
    "task": "rounded=0;whiteSpace=wrap;html=1;fillColor=#dae8fc;strokeColor=#6c8ebf;",
    "decision": "rhombus;whiteSpace=wrap;html=1;fillColor=#ffe6cc;strokeColor=#d79b00;",
}
SIZE = {
    "start": (170, 50),
    "end": (170, 50),
    "task": (210, 60),
    "decision": (180, 90),
}
EDGE_STYLE = "edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;endArrow=block;"
LANE_LABEL_STYLE = (
    "text;html=1;align=center;verticalAlign=middle;fontStyle=1;fontSize=13;"
)


def load(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def side_targets(steps):
    """Cíle druhé a další větve rozhodnutí kreslíme vpravo, ať se tok nekříží.

    Vrací mapu cíl → index postranního sloupce (0, 1, 2…). Rozhodnutí s více než
    dvěma větvemi tak dostane každou větev do vlastního sloupce; kdyby sdílely
    jeden, překryjí se popisky hran.
    """
    side = {}
    for s in steps:
        if s.get("type") == "decision":
            for br in (s.get("branches") or [])[1:]:
                target = br.get("target")
                if target is not None and target not in side:
                    side[target] = len(side)
    return side


def anchor(exit_side, entry_side):
    """Kotvy hrany. Bez nich draw.io volí výchozí bod a čára obchází uzel obloukem."""
    pts = {
        "top": (0.5, 0),
        "bottom": (0.5, 1),
        "left": (0, 0.5),
        "right": (1, 0.5),
    }
    ex, ey = pts[exit_side]
    nx, ny = pts[entry_side]
    return (
        f"exitX={ex};exitY={ey};exitDx=0;exitDy=0;"
        f"entryX={nx};entryY={ny};entryDx=0;entryDy=0;"
    )


def edge_anchors(src_id, tgt_id, order, col, is_branch=False, branch_index=0):
    """Zvolí, kterou stranou hrana z uzlu vyjde a kterou do cíle vstoupí.

    Pravidla vycházejí z toho, jak je diagram rozložený: hlavní tok je sloupec 0
    a jde shora dolů, postranní větve rozhodnutí sedí ve sloupcích vpravo.

    * dopředu ve stejném sloupci  → zdola nahoru (přímá svislice)
    * zpět ve stejném sloupci     → vlevo do vlevo (smyčka obchází zleva)
    * do postranního sloupce      → doprava do shora
    * z postranního sloupce zpět  → vlevo do vpravo
    """
    if tgt_id not in order or src_id not in order:
        return ""
    src_col, tgt_col = col.get(src_id, 0), col.get(tgt_id, 0)
    forward = order[tgt_id] > order[src_id]

    if tgt_col > src_col:
        return anchor("right", "top")
    if tgt_col < src_col:
        # Zpět doleva: nahoru se vrací vlevo, dolů sjede vlastním sloupcem
        # a vejde zprava. Kdyby i dopředná hrana šla vlevo, protnula by
        # boxy hlavního toku, které mezitím leží mezi řádky.
        return anchor("bottom", "right") if forward else anchor("left", "right")
    # stejný sloupec
    if is_branch and branch_index == 0:
        return anchor("bottom", "top") if forward else anchor("left", "left")
    return anchor("bottom", "top") if forward else anchor("left", "left")


def assign_rows(steps, side):
    """Přiřadí každému kroku řádek.

    Hlavní tok (sloupec 0) dostane po sobě jdoucí řádky, takže zůstane kompaktní.
    Postranní krok se zavěsí vedle rozhodnutí, ze kterého vychází (o řádek níž),
    místo aby si držel svoje pořadí v seznamu — jinak vznikají dlouhé svislice.
    """
    rows = {}
    r = 0
    for s in steps:
        if s["id"] not in side:
            rows[s["id"]] = r
            r += 1
    for s in steps:
        for bi, br in enumerate(s.get("branches") or []):
            tgt = br.get("target")
            if tgt in side and tgt not in rows:
                rows[tgt] = rows.get(s["id"], 0) + 1 + bi
    for s in steps:  # postranní kroky bez rozhodnutí (obrana proti neúplnému modelu)
        rows.setdefault(s["id"], r)
        r = max(r, rows[s["id"]] + 1)
    return rows


def lane_columns(steps):
    """Pořadí aktérů podle prvního výskytu — určuje sloupce swimlane."""
    order = []
    for s in steps:
        a = s.get("actor")
        if a and a not in order:
            order.append(a)
    return {a: i for i, a in enumerate(order)}


def build_xml(model: dict, swimlanes: bool) -> str:
    proc = model.get("process") or {}
    steps = proc.get("steps") or []
    if not steps:
        return None  # není co kreslit — rozhodne volající

    actors = {a["id"]: a for a in (model.get("actors") or []) if "id" in a}
    side = side_targets(steps)
    lanes = lane_columns(steps) if swimlanes else {}

    cells = ['<mxCell id="0"/>', '<mxCell id="1" parent="0"/>']

    if swimlanes and lanes:
        for actor_id, col in lanes.items():
            name = actors.get(actor_id, {}).get("name", actor_id)
            cells.append(
                f'<mxCell id="lane-{col}" value="{escape(name)}" '
                f'style="{LANE_LABEL_STYLE}" vertex="1" parent="1">'
                f'<mxGeometry x="{MAIN_X + col * LANE_W}" y="20" '
                f'width="{LANE_W - 40}" height="30" as="geometry"/></mxCell>'
            )

    rows = assign_rows(steps, side)

    for i, s in enumerate(steps):
        stype = s.get("type", "task")
        w, h = SIZE.get(stype, SIZE["task"])
        if swimlanes and lanes:
            x = MAIN_X + lanes.get(s.get("actor"), 0) * LANE_W
            y = TOP_Y + i * DY
        else:
            if s.get("id") in side:
                x = SIDE_X + side[s["id"]] * LANE_W
            else:
                x = MAIN_X
            y = TOP_Y + rows[s["id"]] * DY
        cells.append(
            f'<mxCell id="{s["id"]}" value="{escape(str(s.get("label", "")))}" '
            f'style="{STYLE.get(stype, STYLE["task"])}" vertex="1" parent="1">'
            f'<mxGeometry x="{x}" y="{y}" width="{w}" height="{h}" as="geometry"/>'
            f"</mxCell>"
        )

    order = {s["id"]: rows[s["id"]] for s in steps}
    col = {s["id"]: (side[s["id"]] + 1 if s.get("id") in side else 0) for s in steps}

    eid = 0
    for s in steps:
        sid = s["id"]
        if s.get("branches"):
            for bi, br in enumerate(s["branches"]):
                eid += 1
                anchors = edge_anchors(sid, br.get("target"), order, col,
                                       is_branch=True, branch_index=bi)
                cells.append(
                    f'<mxCell id="e{eid}" value="{escape(str(br.get("label", "")))}" '
                    f'style="{EDGE_STYLE}{anchors}" edge="1" parent="1" '
                    f'source="{sid}" target="{br["target"]}">'
                    f'<mxGeometry relative="1" as="geometry"/></mxCell>'
                )
        elif s.get("next"):
            eid += 1
            anchors = edge_anchors(sid, s["next"], order, col)
            cells.append(
                f'<mxCell id="e{eid}" style="{EDGE_STYLE}{anchors}" edge="1" parent="1" '
                f'source="{sid}" target="{s["next"]}">'
                f'<mxGeometry relative="1" as="geometry"/></mxCell>'
            )

    body = "\n        ".join(cells)
    name = proc.get("name", model.get("title", "Proces"))
    return (
        '<mxfile host="doc-to-model">\n'
        f'  <diagram name="{escape(str(name))}" id="proc-1">\n'
        '    <mxGraphModel dx="900" dy="700" grid="1" gridSize="10" '
        'guides="1" tooltips="1" connect="1" arrows="1" fold="1" '
        'page="1" pageScale="1" pageWidth="850" pageHeight="1100" '
        'math="0" shadow="0">\n'
        f"      <root>\n        {body}\n      </root>\n"
        "    </mxGraphModel>\n"
        "  </diagram>\n"
        "</mxfile>\n"
    )


def main():
    ap = argparse.ArgumentParser(description="Emit .drawio z instance analytical-doc.")
    ap.add_argument("--model", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument(
        "--swimlanes",
        action="store_true",
        help="Rozlož kroky do sloupců podle aktéra.",
    )
    args = ap.parse_args()

    require(args.model, ["validate"], "emit")
    warn_if_missing(args.model, "ground-check",
                    "výstup může nést tvrzení bez opory ve zdroji")
    warn_if_missing(args.model, "coverage-check",
                    "diagram může vynechat celé části procesu ze zdroje")

    xml = build_xml(load(args.model), args.swimlanes)
    if xml is None:
        # Dokument, který nepopisuje sled kroků (analýza, paper, výklad), je
        # legitimní vstup. Chybějící diagram proto není chyba — jen se přeskočí.
        # Kdyby se tu skončilo chybou, spadl by celý build a nevznikly by ani
        # ostatní projekce.
        print("[přeskočeno] draw.io: model nepopisuje proces — není co kreslit")
        return 0
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(xml, encoding="utf-8")
    print(f"[OK] draw.io: {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
