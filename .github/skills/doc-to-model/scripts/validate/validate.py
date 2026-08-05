#!/usr/bin/env python3
"""Sdílený validátor strukturované pravdy (LinkML substrát) — volatelná jednotka.

Jeden engine, který volají domain-model, doc-consistency i emitory — místo 3 kopií
validace. Dvě deterministické vrstvy:

  L1 strukturální ← `linkml-validate` (enum, required, typy, kardinalita)   [shell-out]
  L2 referenční   ← referential.ReferentialChecker (unikátnost id, dangling) [schema-driven]

L3 sémantická (AI contradiction nad fakty) NENÍ tady — je to LLM operace, kterou
invokuje wrapper skill (/validate-model) přes contradiction-verifier agenta. Knihovna
zůstává deterministická a testovatelná.

CLI:
  python3 validate.py --schema S.linkml.yaml --data D.yaml [--class Root]
                      [--skip-structural] [--json]
Exit: 0 = OK, 1 = validační chyby, 2 = chyba použití/běhu.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys

import yaml

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from referential import ReferentialChecker  # noqa: E402


def run_structural(schema: str, data: str, root_class: str | None) -> tuple[bool, list[str]]:
    """L1 přes linkml-validate. Vrať (ok, řádky_výstupu)."""
    exe = shutil.which("linkml-validate")
    if not exe:
        return False, [
            "linkml-validate není v PATH (pip install linkml). L1 přeskočena."
        ]
    cmd = [exe, "-s", schema]
    if root_class:
        cmd += ["-C", root_class]
    cmd.append(data)
    env = {**os.environ, "PYTHONWARNINGS": "ignore"}
    proc = subprocess.run(cmd, capture_output=True, text=True, env=env)
    out = (proc.stdout + proc.stderr).strip()
    noise = ("RequestsDependencyWarning", "warnings.warn", "urllib3")
    lines = [ln for ln in out.splitlines() if ln.strip() and not any(n in ln for n in noise)]
    return proc.returncode == 0, lines


def validate(
    schema: str,
    data: str,
    root_class: str | None = None,
    skip_structural: bool = False,
) -> dict:
    result: dict = {"schema": schema, "data": data, "structural": None, "referential": None}

    if not skip_structural:
        ok, lines = run_structural(schema, data, root_class)
        result["structural"] = {"ok": ok, "messages": lines}

    checker = ReferentialChecker(schema)
    with open(data, encoding="utf-8") as fh:
        payload = yaml.safe_load(fh)
    ref_errors = checker.check(payload, root_class)
    result["referential"] = {"ok": not ref_errors, "errors": ref_errors}

    struct_ok = result["structural"]["ok"] if result["structural"] else True
    result["ok"] = bool(struct_ok and result["referential"]["ok"])
    return result


def _print_human(r: dict) -> None:
    s = r.get("structural")
    if s is not None:
        tag = "OK" if s["ok"] else "FAIL"
        print(f"[L1 strukturální] {tag}")
        for m in s["messages"]:
            print(f"  {m}")
    else:
        print("[L1 strukturální] přeskočeno")

    ref = r["referential"]
    tag = "OK" if ref["ok"] else "FAIL"
    print(f"[L2 referenční] {tag} ({len(ref['errors'])} chyb)")
    for e in ref["errors"]:
        print(f"  - {e}")

    print(f"\n{'✓ VALIDNÍ' if r['ok'] else '✗ NEVALIDNÍ'}: {r['data']}")


def main() -> int:
    ap = argparse.ArgumentParser(description="Sdílený LinkML validátor (L1+L2).")
    ap.add_argument("--schema", "-s", required=True)
    ap.add_argument("--data", "-d", required=True)
    ap.add_argument("--class", "-C", dest="root_class", default=None,
                    help="Cílová třída kořenového objektu (default: tree_root ze schématu).")
    ap.add_argument("--skip-structural", action="store_true",
                    help="Vynech L1 (jen referenční check).")
    ap.add_argument("--json", action="store_true", help="Strojový výstup.")
    args = ap.parse_args()

    for p in (args.schema, args.data):
        if not os.path.exists(p):
            print(f"chyba: soubor neexistuje: {p}", file=sys.stderr)
            return 2

    try:
        r = validate(args.schema, args.data, args.root_class, args.skip_structural)
    except Exception as exc:  # noqa: BLE001
        print(f"chyba běhu: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(r, ensure_ascii=False, indent=2))
    else:
        _print_human(r)
    return 0 if r["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
