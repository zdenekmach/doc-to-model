#!/usr/bin/env bash
# Přetáhne skill ze zdrojového systému do tohohle repa.
#
#   bash tools/sync-from-personalskills.sh [cesta_k_PersonalSkills]
#
# Skript žije ZÁMĚRNĚ tady, ne v PersonalSkills. Závislost tak míří jedním
# směrem — tohle repo umí sáhnout do systému, systém o tomhle repu neví a nic
# na něm nestojí. Spouští se ručně, nikdy automaticky.
#
# Přenos má tři kroky: zkopíruj, odpoj od systému, ověř. Prostřední krok dělá
# tools/adapt.py — ruční patchování po každém syncu je práce, na kterou se za
# měsíc zapomene. Poslední krok je nezávislá kontrola: hledá vazby na
# PersonalSkills v hotovém výsledku, ať už je tam nechal kdokoli.
set -euo pipefail

SRC_ROOT="${1:-$HOME/Projects/PersonalSkills}"
SRC_SKILL="$SRC_ROOT/.claude/plugins/research/skills/doc-to-model"
SRC_VALIDATE="$SRC_ROOT/.claude/scripts/model-validate"

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEST="$REPO/.github/skills/doc-to-model"

[[ -d "$SRC_SKILL" ]] || { echo "Zdroj nenalezen: $SRC_SKILL"; exit 2; }

echo "── Přenos ──────────────────────────────────────────"
echo "  z: $SRC_SKILL"
echo "  do: $DEST"

rsync -a --delete \
  --exclude '__pycache__' \
  --exclude 'scripts/validate' \
  "$SRC_SKILL/" "$DEST/"

mkdir -p "$DEST/scripts/validate"
cp "$SRC_VALIDATE/validate.py" "$SRC_VALIDATE/referential.py" "$DEST/scripts/validate/"

find "$DEST" -name '__pycache__' -type d -exec rm -rf {} + 2>/dev/null || true

echo "── Odpojení od zdrojového systému ──────────────────"
python3 "$REPO/tools/adapt.py"

echo "── Kontrola vazeb na zdrojový systém ───────────────"
HITS=$(grep -rn 'PersonalSkills\|\.claude/plugins\|\.claude/scripts/model-validate\|{PROJECT_DIR}' \
       "$DEST" 2>/dev/null || true)

if [[ -n "$HITS" ]]; then
  echo "$HITS"
  echo ""
  echo "ZBYLY vazby na zdrojový systém, které adapt.py nezná."
  echo "Doplň je do tools/adapt.py — ne ručně do souborů, jinak je smaže další sync."
  exit 1
fi

echo "  žádné vazby na PersonalSkills nezbyly"
echo "────────────────────────────────────────────────────"
echo "Hotovo. Zkontroluj 'git diff' a projeď smoke test z README."
