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
import lang
from sourcemap import anchor_sources, source_windows

STEM = 5
MIN_TOKEN = 4
OK_RATIO = 0.34
WEAK_RATIO = 0.15

# Kolik zdrojových míst se musí dát ve zdroji najít, aby model vůbec dával smysl.
# Nezakotvený locator neznamená slabý důkaz, znamená ŽÁDNÝ — nedá se ověřit
# a v prohlížeči neodskočí. Do 2026-08-05 se to počítalo jen jako slabý nález,
# takže model, kde ani jeden z 20 výroků nešel ověřit, prošel branou a vyrobil
# Word i web (reálný případ: locatory ve tvaru „Rodič / Dítě", které v dokumentu
# doslova nejsou).
ANCHOR_MIN_RATIO = 0.5

# Slova bez rozlišovací síly i značky normativních vět bydlí v `lang/<kód>.yaml`.
# Dokud to byly konstanty tady, dokument v jiném jazyce tiše prošel — nic se
# neodfiltrovalo, takže se shoda nafoukla. Viz lang.py.
_PACK = None


def use_pack(pack) -> None:
    """Nastav jazyk pro tenhle běh. Volá se jednou, na začátku."""
    global _PACK
    _PACK = pack


def active_pack():
    if _PACK is None:
        # Prázdný stopword list by nespadl, jen by tiše zhoršil výsledek —
        # a to je přesně ta třída chyb, kvůli které jazykové balíčky vznikly.
        raise RuntimeError(
            "jazykový balíček nebyl nastaven — zavolej use_pack() (viz lang.resolve)"
        )
    return _PACK


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
        elif len(tok) >= MIN_TOKEN and tok not in active_pack().stopwords:
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
    ap.add_argument("--lang", help="Kód jazykového balíčku (default: detekce ze zdroje).")
    args = ap.parse_args()

    if args.source.suffix.lower() == ".pdf":
        sys.exit("[CHYBA] --source čeká text. PDF si napřed vytáhni do .txt.")

    m = load(args.model)
    raw = args.source.read_text(encoding="utf-8")
    pack, how = lang.resolve(raw, args.lang)
    use_pack(pack)
    print(f"[jazyk] {how}")
    lines = raw.splitlines()
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

    # Zakotvenost se hlásí VŽDY, i když je v pořádku. Naměřená hodnota v logu je
    # jediné, čím se pozná rozdíl mezi „locatory sedí" a „nikdo je neměřil".
    anchored = sum(1 for v in anchors.values() if v is not None)
    ratio = anchored / len(anchors) if anchors else 1.0
    anchors_bad = bool(anchors) and ratio < ANCHOR_MIN_RATIO

    if args.json:
        print(json.dumps({"results": results, "blocking": len(bad),
                          "anchored": anchored, "sources": len(anchors)},
                         ensure_ascii=False, indent=2))
    else:
        print(f"[opora] ověřeno {len(results)} výroků → {out}")
        print(f"  zakotveno {anchored}/{len(anchors)} zdrojů "
              f"({ratio * 100:.0f} %) · bez opory / visící odkaz: {len(bad)} · "
              f"k prohlédnutí: {len(weak)}")
        for r in bad:
            print(f"  ✗ {r['id']}: {r['note']}")

    ok = (not bad and not anchors_bad) or args.warn_only
    record(args.model, "ground-check", ok=ok,
           detail={"blocking": len(bad), "weak": len(weak), "total": len(results),
                   "anchored": anchored, "sources": len(anchors)})

    if anchors_bad and not args.warn_only:
        sys.exit(
            f"\n[BRÁNA] ve zdroji se našlo jen {anchored} z {len(anchors)} "
            f"zdrojových míst ({ratio * 100:.0f} %, práh {ANCHOR_MIN_RATIO * 100:.0f} %).\n"
            "Nezakotvený locator znamená, že se výrok nedá ověřit a v prohlížeči\n"
            "neodskočí — model vypadá trasovatelně, ale není.\n"
            "`locator` musí být DOSLOVNÝ řetězec z dokumentu (nadpis, „§ 12\", „s. 7\").\n"
            "Skládaná cesta „Rodič / Dítě\" ani dopsaná glosa v závorce v dokumentu\n"
            "nejsou, takže se nenajdou. Návrhy, které se zakotvit dají, vypíše\n"
            "scripts/segment.py."
        )

    if bad and not args.warn_only:
        sys.exit(
            f"\n[BRÁNA] {len(bad)} výroků nemá oporu v citovaném místě. "
            "Oprav extrakci, nebo spusť s --warn-only, když jde o planý poplach."
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
