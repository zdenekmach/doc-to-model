#!/usr/bin/env python3
"""ground_check.py — má každý požadavek oporu v citovaném místě zdroje?

Extrakce je jediný nedeterministický krok celého řetězu. Tenhle skript je jeho
postpodmínka: pro každý požadavek vezme jeho vlastní slova a čísla a ověří, že
se vyskytují v okolí místa, na které se odkazuje.

Není to sémantická kontrola a netvrdí, že požadavek je správně. Chytá hrubší
a nebezpečnější případ — **tvrzení, které v citovaném místě nemá oporu vůbec**.
Přesně tak vzniká model, který vypadá spolehlivěji než dokument pod ním.

Čeština se ohýbá, proto se porovnávají kmeny (prvních 5 znaků slova), ne celá
slova. Čísla se porovnávají přesně — jsou to nejsilnější kotvy a zároveň to,
co se nejhůř kontroluje očima.

    python3 ground_check.py --model model.yaml --source zdroj.txt [--json] [--warn-only]

Návratový kód 1, když má některý požadavek verdikt „bez opory" (pokud není
--warn-only). Report se píše vedle modelu jako <model>-opora.md.
"""
import argparse
import json
import re
import sys
from pathlib import Path

import yaml

from pipeline_state import record
from sourcemap import anchor_sources, source_windows

STEM = 5
MIN_TOKEN = 4
OK_RATIO = 0.34
WEAK_RATIO = 0.15

# Slova, která nesou málo rozlišovací síly — kdyby se počítala, „opora" by
# vznikla i tam, kde se jen potkaly spojky.
STOP = {
    "který", "která", "které", "kteří", "kterou", "kterých", "jejich", "svých",
    "tento", "tato", "toto", "této", "tohoto", "těchto", "podle", "podle",
    "musí", "může", "budou", "bude", "byla", "byly", "bylo", "jsou", "není",
    "nebo", "také", "však", "aby", "ale", "pro", "před", "přes", "při", "nad",
    "pod", "ode", "ode", "dne", "dnů", "všech", "každý", "každé", "další",
    "systém", "systému", "údaje", "údajů", "případě", "rámci", "vztahu",
}


def load(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def by_id(items):
    return {it["id"]: it for it in (items or []) if "id" in it}


def stems(text: str):
    """Rozlišovací kmeny a čísla z textu."""
    words, numbers = set(), set()
    for tok in re.findall(r"[0-9]+(?:[.,][0-9]+)?|[^\W\d_]+", (text or "").lower()):
        if tok[0].isdigit():
            numbers.add(tok.rstrip(".,"))
        elif len(tok) >= MIN_TOKEN and tok not in STOP:
            words.add(tok[:STEM])
    return words, numbers


def requirement_text(r: dict) -> str:
    """Text výroku k ověření — požadavku, nefunkčního požadavku i tvrzení.

    `basis` se záměrně nepočítá: je to naše poznámka o tom, o co se tvrzení
    opírá, ne slova ze zdroje. Kdyby se přidala, kontrola by si sama vyráběla
    shodu.
    """
    parts = [r.get("title"), r.get("description")]
    parts += list(r.get("acceptance") or [])
    parts.append(r.get("requirement"))  # nefunkční požadavek
    return " ".join(p for p in parts if p)


def check_one(r, sources, windows, lines):
    sid = r.get("source")
    rid = r.get("id", "?")
    if not sid:
        return dict(id=rid, verdict="bez zdroje", ratio=None,
                    note="požadavek neuvádí, odkud pochází")
    if sid not in sources:
        return dict(id=rid, verdict="visící odkaz", ratio=None,
                    note=f"zdroj {sid} v modelu neexistuje")
    win = windows.get(sid)
    if win is None:
        return dict(id=rid, verdict="nezakotveno", ratio=None,
                    note=f"locator zdroje {sid} se ve zdroji nenašel")

    start, end = win
    haystack = "\n".join(lines[start:end]).lower()
    hay_words, hay_numbers = stems(haystack)

    words, numbers = stems(requirement_text(r))
    if not words and not numbers:
        return dict(id=rid, verdict="prázdný", ratio=None,
                    note="požadavek nemá text k ověření")

    hit_w = len(words & hay_words)
    hit_n = len(numbers & hay_numbers)
    total = len(words) + len(numbers)
    ratio = (hit_w + hit_n) / total if total else 0.0

    missing_numbers = sorted(numbers - hay_numbers)

    if ratio >= OK_RATIO:
        verdict = "opora"
    elif ratio >= WEAK_RATIO:
        verdict = "slabá opora"
    else:
        verdict = "bez opory"

    # Číslo je nejsilnější kotva a zároveň to, co se vymyslí nejsnáz — lhůta,
    # částka, počet. Když požadavek čísla nese a ANI JEDNO není v citovaném
    # místě, nestačí, že se trefil do slovní zásoby okolí; taková shoda vzniká
    # i u textu, který s místem jen sousedí tématem.
    # Vysoká slovní shoda výjimku dostane — tam jde spíš o jiný zápis čísla.
    if numbers and hit_n == 0 and ratio < OK_RATIO:
        verdict = "bez opory"

    note = f"shoda {hit_w + hit_n}/{total} · řádky {start}–{end}"
    if missing_numbers:
        note += f" · čísla mimo citované místo: {', '.join(missing_numbers)}"
    return dict(id=rid, verdict=verdict, ratio=round(ratio, 2), note=note)


def render(results, model_title):
    order = {"bez opory": 0, "visící odkaz": 1, "nezakotveno": 2, "bez zdroje": 3,
             "slabá opora": 4, "prázdný": 5, "opora": 6}
    rows = sorted(results, key=lambda r: (order.get(r["verdict"], 9), r["id"]))
    counts = {}
    for r in results:
        counts[r["verdict"]] = counts.get(r["verdict"], 0) + 1

    out = [f"# Opora výroků ve zdroji — {model_title}", ""]
    out.append("Ověřuje, že slova a čísla výroku se vyskytují v citovaném místě.")
    out.append("Není to kontrola správnosti — chytá tvrzení, která v odkazovaném")
    out.append("místě nemají oporu vůbec.")
    out.append("")
    out.append(" · ".join(f"**{k}**: {v}" for k, v in sorted(counts.items())))
    out.append("")
    out.append("| Výrok | Verdikt | Shoda | Poznámka |")
    out.append("|-----------|---------|-------|----------|")
    for r in rows:
        ratio = "—" if r["ratio"] is None else f"{r['ratio']:.2f}"
        out.append(f"| `{r['id']}` | {r['verdict']} | {ratio} | {r['note']} |")
    return "\n".join(out) + "\n"


def main():
    ap = argparse.ArgumentParser(description="Ověř oporu požadavků v citovaném zdroji.")
    ap.add_argument("--model", required=True, type=Path)
    ap.add_argument("--source", required=True, type=Path, help="Zdrojový text (.md/.txt)")
    ap.add_argument("--out", type=Path, help="Report (default <model>-opora.md)")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--warn-only", action="store_true",
                    help="Nálezy jen vypiš, nekonči chybou.")
    args = ap.parse_args()

    if args.source.suffix.lower() == ".pdf":
        sys.exit("[CHYBA] --source čeká text. PDF si napřed vytáhni do .txt.")

    m = load(args.model)
    lines = args.source.read_text(encoding="utf-8").splitlines()
    sources = by_id(m.get("sources"))
    anchors = anchor_sources(lines, sources)
    windows = source_windows(lines, anchors)

    # Tvrzení se ověřují stejně jako požadavky — kontrola opory je na typu
    # výroku nezávislá a na tvrzeních funguje dokonce lépe, protože jsou
    # zdroji jazykově blíž než přeformulovaný požadavek.
    items = (list(m.get("claims") or [])
             + list(m.get("requirements") or [])
             + list(m.get("quality_requirements") or []))
    results = [check_one(r, sources, windows, lines) for r in items]

    out = args.out or args.model.with_name(args.model.stem + "-opora.md")
    out.write_text(render(results, m.get("title", "")), encoding="utf-8")

    bad = [r for r in results if r["verdict"] in ("bez opory", "visící odkaz")]
    weak = [r for r in results if r["verdict"] in ("slabá opora", "nezakotveno", "bez zdroje")]

    if args.json:
        print(json.dumps({"results": results, "blocking": len(bad)},
                         ensure_ascii=False, indent=2))
    else:
        print(f"[opora] ověřeno {len(results)} výroků → {out}")
        print(f"  bez opory / visící odkaz: {len(bad)} · k prohlédnutí: {len(weak)}")
        for r in bad:
            print(f"  ✗ {r['id']}: {r['note']}")

    ok = not bad or args.warn_only
    record(args.model, "ground-check", ok=ok,
           detail={"blocking": len(bad), "weak": len(weak), "total": len(results)})

    if bad and not args.warn_only:
        sys.exit(
            f"\n[BRÁNA] {len(bad)} výroků nemá oporu v citovaném místě. "
            "Oprav extrakci, nebo spusť s --warn-only, když jde o planý poplach."
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
