#!/usr/bin/env python3
"""Odpojí přenesený skill od zdrojového systému.

Skill je v PersonalSkills zapojený do okolí: volá sdílený validátor, používá
konvenci `{PROJECT_DIR}` a odkazuje na sesterské skilly. Samostatné repo nic
z toho nemá, takže se to při každém přenosu musí přepsat.

Dělá to skript, ne člověk po ruce. Ruční patchování po každém syncu je přesně
ta práce, na kterou se za měsíc zapomene — a rozdíl mezi „skill je odpojený"
a „skill vypadá odpojeně" pozná až první běh u někoho cizího.

Je to **idempotentní**: druhý běh nad už upraveným souborem nic nezmění a
nespadne. Proto se každá náhrada hlásí jako `upraveno` / `už bylo`.

Použití:
    python3 tools/adapt.py [--check]

    --check  jen ohlásí, co by se změnilo (exit 1, když by se něco měnilo)
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SKILL = REPO / ".github/skills/doc-to-model"

# (soubor, co hledat, čím nahradit, popis)
SUBSTITUTIONS: list[tuple[str, str, str, str]] = [
    (
        "scripts/build.sh",
        'SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"\n'
        'REPO_ROOT="$(cd "$SKILL_DIR/../../../../.." && pwd)"\n'
        'SCHEMA="${4:-$SKILL_DIR/schema/analytical-doc.linkml.yaml}"\n'
        'VALIDATE="$REPO_ROOT/.claude/scripts/model-validate/validate.py"\n'
        'S="$SKILL_DIR/scripts"',
        'SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"\n'
        'SCHEMA="${4:-$SKILL_DIR/schema/analytical-doc.linkml.yaml}"\n'
        'S="$SKILL_DIR/scripts"\n'
        "# Validátor je vendorovaný uvnitř skillu — skill musí běžet bez okolního repa.\n"
        'VALIDATE="$S/validate/validate.py"',
        "build.sh → vendorovaný validátor",
    ),
    (
        # Licence patří k publikovanému repu, ne do zdrojového systému — proto se
        # doplňuje tady. `license` je volitelné pole frontmatteru, které Copilot zná.
        "SKILL.md",
        'description: "Triggers:',
        'license: MIT\ndescription: "Triggers:',
        "SKILL.md → license: MIT ve frontmatteru",
    ),
    (
        "SKILL.md",
        "Cílový adresář: `{PROJECT_DIR}/<slug>/model/<nazev>/`. Bez aktivního projektu se zeptej.",
        "Cílový adresář zvol vedle zdrojového dokumentu, například `model/<nazev>/`.\n"
        "Model, jeho stav a výstupy patří k sobě.",
        "SKILL.md → cílový adresář bez {PROJECT_DIR}",
    ),
    (
        "SKILL.md",
        "python3 .claude/scripts/model-validate/validate.py \\\n"
        "  --schema .claude/plugins/research/skills/doc-to-model/schema/analytical-doc.linkml.yaml \\\n"
        "  --data model.yaml --class Document",
        "python3 scripts/validate/validate.py \\\n"
        "  --schema schema/analytical-doc.linkml.yaml \\\n"
        "  --data model.yaml --class Document",
        "SKILL.md → příkaz validace",
    ),
    (
        "SKILL.md",
        "bash .claude/plugins/research/skills/doc-to-model/scripts/build.sh model.yaml [out_dir] [zdroj.txt]",
        "bash scripts/build.sh model.yaml [out_dir] [zdroj.txt]",
        "SKILL.md → příkaz build.sh",
    ),
    (
        # V publikovaném repu je v kořeni zkratka, takže cesta ke skillu odpadá.
        "SKILL.md",
        "bash .claude/plugins/research/skills/doc-to-model/scripts/rebuild.sh model.yaml",
        "bash rebuild.sh model.yaml",
        "SKILL.md → příkaz rebuild.sh",
    ),
    (
        "SKILL.md",
        "| `templates/model-skeleton.yaml` | Kostra instance k vyplnění |",
        "| `scripts/validate/` | Validátor (L1 linkml-validate, L2 referenční) — vendorovaný, ne systémový |\n"
        "| `templates/model-skeleton.yaml` | Kostra instance k vyplnění |",
        "SKILL.md → validátor v tabulce referencí",
    ),
    (
        "SKILL.md",
        "## Viz také\n\n"
        "- `/data-metamodel` — návrh schématu, když analytical-doc nesedí\n"
        "- `/domain-model` — plnění modelu z researche, ne z jednoho dokumentu\n"
        "- `/doc-consistency` — kontrola rozporů (navazuje)\n"
        "- `.claude/docs/DATA-PROJECTION-PATTERN.md` — pattern a rozhodovací hrana",
        "## Viz také\n\n"
        "Skill je výřez z většího celku a tyhle sousedy s sebou nenese:\n\n"
        "- **návrh schématu**, když `analytical-doc` na dokument nesedí\n"
        "- **plnění modelu z researche** místo z jednoho hotového dokumentu\n"
        "- **kontrola rozporů** nad `*-claims.json`, který emituje `emit_claims.py`\n\n"
        "Emitor tvrzení tu zůstal schválně: jeho výstup je vstup pro takovou kontrolu,\n"
        "ať už ji pustíš čímkoli.",
        "SKILL.md → Viz také bez odkazů na sesterské skilly",
    ),
]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true", help="jen ohlas, nic nezapisuj")
    args = ap.parse_args()

    pending = 0
    for rel, old, new, label in SUBSTITUTIONS:
        path = SKILL / rel
        if not path.exists():
            print(f"  CHYBÍ  {rel} — přenos je neúplný")
            return 2
        text = path.read_text(encoding="utf-8")

        # Hotový stav se testuje PRVNÍ. U vkládacích náhrad je `old` podřetězcem
        # `new` (kotevní řádek vložení přežije), takže opačné pořadí by řádek
        # přidávalo při každém běhu znovu.
        if new in text:
            if not args.check:
                print(f"  už bylo   {label}")
        elif old in text:
            pending += 1
            if args.check:
                print(f"  změnilo by se  {label}")
            else:
                path.write_text(text.replace(old, new, 1), encoding="utf-8")
                print(f"  upraveno  {label}")
        else:
            # Ani původní, ani upravená podoba — předloha se ve zdroji změnila.
            # Tiše to přeskočit by znamenalo pustit dál skill s vazbou na systém.
            print(f"  NESEDÍ    {label} — předloha se ve zdroji změnila, oprav tools/adapt.py")
            return 2

    if args.check:
        print(f"\n{pending} úprav by se provedlo." if pending else "\nNic k úpravě.")
        return 1 if pending else 0

    print(f"\nHotovo. {pending} úprav.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
