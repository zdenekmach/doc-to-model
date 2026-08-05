#!/usr/bin/env python3
"""mark_step.py — zapiš do stavu, že krok proběhl nad aktuální verzí modelu.

Existuje kvůli krokům, které dělá cizí skript. `model-validate` je sdílená
knihovna napříč skilly a nemá o téhle pipeline vědět — proto se jeho výsledek
zapisuje zvenčí, hned po úspěšném běhu.

    python3 mark_step.py --model model.yaml --step validate [--failed]
"""
import argparse
import sys
from pathlib import Path

from pipeline_state import record


def main():
    ap = argparse.ArgumentParser(description="Zapiš výsledek kroku do stavu modelu.")
    ap.add_argument("--model", required=True, type=Path)
    ap.add_argument("--step", required=True)
    ap.add_argument("--failed", action="store_true")
    args = ap.parse_args()

    record(args.model, args.step, ok=not args.failed)
    return 0


if __name__ == "__main__":
    sys.exit(main())
