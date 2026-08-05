#!/usr/bin/env python3
"""segment.py — text → návrh bloku `sources` pro model.

Rozseká zdroj na místa, na která se dá odkazovat: stránky, nadpisy, paragrafy.
Je to první krok extrakce, protože citace dodělávané zpětně dopadnou špatně.

Výstup je hotový YAML fragment k vložení do modelu. Návrh, ne verdikt — člověk
ho zkrátí nebo přejmenuje.

    python3 segment.py --source zdroj.txt [--out sources.yaml] [--max 40]

**Self-check:** každý navržený locator si skript sám zkusí dohledat toutéž
funkcí, kterou pak používá prohlížeč i kontrola opory. Kdyby vyrobil locator,
který se nedá zakotvit, byla by z citace ozdoba.
"""
import argparse
import re
import sys
from pathlib import Path

from sourcemap import anchor_sources

PAGE_RX = re.compile(r"^===\s*STRANA\s+(\d+)\s*===")
MD_RX = re.compile(r"^(#{1,3})\s+(.*\S)")
# Číslovaná i římská kapitola na začátku řádku: „3. Termíny", „IV. Povinnosti".
NUM_RX = re.compile(r"^((?:\d+(?:\.\d+)*)|(?:[IVX]{1,5}))\.\s+(\S.*)$")
PARA_RX = re.compile(r"§\s*(\d+)")

MAX_TITLE = 70


def clean(text: str) -> str:
    text = re.sub(r"\s+", " ", text).strip(" .:—-")
    return text[:MAX_TITLE]


def segment(lines):
    """Vrátí kandidáty [(řádek, locator, titulek, druh)]."""
    found = []
    seen_para = set()

    for i, raw in enumerate(lines):
        line = raw.strip()
        if not line:
            continue

        m = PAGE_RX.match(line)
        if m:
            # Titulek stránky vezmi z prvního neprázdného řádku pod značkou.
            label = ""
            for nxt in lines[i + 1:i + 4]:
                if nxt.strip():
                    label = clean(nxt)
                    break
            found.append((i, f"s. {m.group(1)}", label or f"strana {m.group(1)}", "strana"))
            continue

        m = MD_RX.match(line)
        if m:
            found.append((i, clean(m.group(2)), clean(m.group(2)), "nadpis"))
            continue

        m = NUM_RX.match(line)
        if m and len(line) < 120:
            found.append((i, clean(line), clean(m.group(2)), "kapitola"))
            continue

        m = PARA_RX.search(line)
        if m and m.group(1) not in seen_para:
            seen_para.add(m.group(1))
            found.append((i, f"§ {m.group(1)}", f"§ {m.group(1)} — {clean(line)}", "paragraf"))

    return found


def dedupe(cands):
    """Jedno místo = jeden zdroj. Přednost má konkrétnější druh před stránkou."""
    rank = {"nadpis": 0, "kapitola": 1, "paragraf": 2, "strana": 3}
    by_line = {}
    for line, loc, title, kind in cands:
        best = by_line.get(line)
        if best is None or rank[kind] < rank[best[3]]:
            by_line[line] = (line, loc, title, kind)
    return [by_line[k] for k in sorted(by_line)]


def render(items):
    out = ["# Návrh zdrojových míst — vlož do modelu jako `sources:`",
           "# Zkrať na ta, na která budeš opravdu odkazovat.",
           "sources:"]
    for idx, (_line, loc, title, kind) in enumerate(items, 1):
        out.append(f"  - id: S{idx}")
        out.append(f"    title: {title!r}")
        out.append(f"    locator: {loc!r}   # {kind}")
    return "\n".join(out) + "\n"


def main():
    ap = argparse.ArgumentParser(description="Navrhni zdrojová místa ze zdrojového textu.")
    ap.add_argument("--source", required=True, type=Path)
    ap.add_argument("--out", type=Path)
    ap.add_argument("--max", type=int, default=40,
                    help="Kolik nejvýš míst navrhnout (default 40).")
    args = ap.parse_args()

    if args.source.suffix.lower() == ".pdf":
        sys.exit("[CHYBA] --source čeká text. Napřed spusť ingest.py.")

    lines = args.source.read_text(encoding="utf-8").splitlines()
    items = dedupe(segment(lines))

    dropped = 0
    if len(items) > args.max:
        dropped = len(items) - args.max
        items = items[: args.max]

    # Self-check: dohledej vlastní návrhy toutéž cestou jako zbytek pipeline.
    sources = {f"S{i}": {"locator": loc} for i, (_l, loc, _t, _k) in enumerate(items, 1)}
    anchors = anchor_sources(lines, sources)
    ok = sum(1 for v in anchors.values() if v is not None)

    text = render(items)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
        print(f"[segment] {len(items)} míst → {args.out}")
    else:
        print(text)

    print(f"[segment] zakotvitelných {ok}/{len(items)}")
    if dropped:
        print(f"[segment] vynecháno {dropped} dalších míst (limit --max {args.max})")
    if ok < len(items):
        print("[POZOR] Některý navržený locator se nedá dohledat — oprav ho ručně, "
              "jinak z citace bude ozdoba.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
