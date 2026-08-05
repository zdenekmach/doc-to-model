#!/usr/bin/env python3
"""emit_claims.py — projekce tvrzení do vstupu pro kontrolu rozporů.

`/doc-consistency` má deterministickou vrstvu, která hledá tvrdé rozpory: stejný
subjekt a predikát ve stejném rozsahu s jinou číselnou hodnotou. Potřebuje k tomu
tvrzení rozložená na části, ne prózu.

Tenhle emitor je to rozhraní. Model, který už tvrzení nese, je nemusí extrahovat
podruhé — a hlavně se tím kontrola rozporů dostane ke **stejným** tvrzením, která
jsou v dokumentu a v diagramu. Dvojí extrakce by znamenala dvě verze pravdy.

    python3 emit_claims.py --model model.yaml --out out/claims.json

Vynechá tvrzení bez `subject`, `predicate` nebo `value` — kontrola je bez nich
neumí porovnat a poloprázdný záznam by jen kazil statistiku. Kolik jich vypadlo,
skript řekne nahlas.
"""
import argparse
import json
import re
import sys
from pathlib import Path

import yaml

from pipeline_state import require, warn_if_missing

REQUIRED = ("subject", "predicate", "value")


def load(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def parse_number(value, explicit):
    """Číselná část hodnoty. Explicitní `value_num` má přednost před odhadem."""
    if explicit is not None:
        return explicit
    if value is None:
        return None
    m = re.search(r"-?\d+(?:[.,]\d+)?", str(value))
    if not m:
        return None
    try:
        return float(m.group(0).replace(",", "."))
    except ValueError:
        return None


def to_claim(c: dict, sources: dict) -> dict:
    src = sources.get(c.get("source"), {})
    citation = " · ".join(
        p for p in (src.get("title"), src.get("locator")) if p
    ) or c.get("source")
    return {
        "id": c.get("id"),
        "subject": c.get("subject"),
        "predicate": c.get("predicate"),
        "value": c.get("value"),
        "value_num": parse_number(c.get("value"), c.get("value_num")),
        "unit": c.get("unit"),
        "scope": c.get("scope"),
        "condition": c.get("condition"),
        # Kontrola rozporů zobrazuje `source` jako doslovný text tvrzení,
        # ne jako odkaz — proto sem jde popis, a citace zvlášť.
        "source": (c.get("description") or c.get("title") or "").strip(),
        "citation": citation,
        "claim_type": c.get("claim_type"),
        "confidence": c.get("confidence"),
    }


def main():
    ap = argparse.ArgumentParser(
        description="Emit claims.json pro deterministickou kontrolu rozporů."
    )
    ap.add_argument("--model", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args()

    require(args.model, ["validate"], "emit")
    warn_if_missing(args.model, "ground-check",
                    "tvrzení mohou nemít oporu ve zdroji")
    warn_if_missing(args.model, "coverage-check",
                    "kontrola rozporů uvidí jen tvrzení, která model vytáhl")

    m = load(args.model)
    sources = {s["id"]: s for s in (m.get("sources") or []) if "id" in s}
    all_claims = m.get("claims") or []

    usable, skipped = [], []
    for c in all_claims:
        if all(c.get(k) for k in REQUIRED):
            usable.append(to_claim(c, sources))
        else:
            missing = [k for k in REQUIRED if not c.get(k)]
            skipped.append((c.get("id", "?"), missing))

    payload = {
        "doc": m.get("source_document") or m.get("title"),
        "model": str(args.model),
        "extracted_by": "doc-to-model (emit_claims.py)",
        "claims": usable,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    # Prázdný soubor není v pořádku, i když vznikl bez chyby. Kontrola rozporů
    # nad ním doběhne, nenajde nic a bude vypadat čistě — tichý úspěch, který
    # znamená opak. Proto se nula hlásí jinou nálepkou než částečný výsledek.
    tag = "[POZOR]" if all_claims and not usable else "[OK]"
    print(f"{tag} tvrzení pro kontrolu rozporů: {args.out} "
          f"({len(usable)} z {len(all_claims)})")

    for cid, missing in skipped[:5]:
        print(f"  [přeskočeno] {cid}: chybí {', '.join(missing)}")
    if len(skipped) > 5:
        print(f"  … a dalších {len(skipped) - 5} tvrzení")

    if all_claims and not usable:
        chybi = sorted({k for _, ms in skipped for k in ms})
        print(f"  Do kontroly rozporů nedošlo ANI JEDNO z {len(all_claims)} tvrzení — "
              f"nejčastěji chybí: {', '.join(chybi)}.")
        print("  Kontrola nad prázdným souborem nenajde nic a bude vypadat čistě.")
        print("  Čtveřice subject · predicate · value · scope je celek, ne výběr "
              "(viz references/extraction.md).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
