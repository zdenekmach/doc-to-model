#!/usr/bin/env bash
# build.sh — jeden průchod druhou polovinou řetězu: validace → opora → projekce.
#
#   bash build.sh <model.yaml> [out_dir] [zdrojovy_text] [schema.linkml.yaml]
#
# Není to orchestrátor. Orchestruje SKILL.md; tohle je zkratka pro „spusť všechno,
# co po extrakci zbývá". Pořadí drží samotné skripty přes <model>.state.json —
# emitor nad neověřeným nebo mezitím změněným modelem odmítne běžet.
#
# Bez třetího argumentu se přeskočí kontrola opory a emitory to vypíší jako
# varování. Diagram i Word pak vzniknou, jen se neví, jestli mají oporu ve zdroji.
#
# Čtvrtý argument je vlastní schéma. Emitory vypisují sekce podle toho, co je
# v instanci — kolekce, které `analytical-doc` nezná, se vypíšou obecně místo aby
# se tiše zahodily.
set -euo pipefail

MODEL="${1:?Použití: build.sh <model.yaml> [out_dir] [zdrojovy_text] [schema]}"
OUT_DIR="${2:-$(dirname "$MODEL")/out}"
SOURCE_TXT="${3:-}"

SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCHEMA="${4:-$SKILL_DIR/schema/analytical-doc.linkml.yaml}"
S="$SKILL_DIR/scripts"
# Validátor je vendorovaný uvnitř skillu — skill musí běžet bez okolního repa.
VALIDATE="$S/validate/validate.py"

BASE="$(basename "${MODEL%.*}")"

echo "── Validace ────────────────────────────────────────"
python3 "$VALIDATE" --schema "$SCHEMA" --data "$MODEL" --class Document
python3 "$S/mark_step.py" --model "$MODEL" --step validate

if [[ -n "$SOURCE_TXT" ]]; then
  echo "── Opora ve zdroji ─────────────────────────────────"
  python3 "$S/ground_check.py" --model "$MODEL" --source "$SOURCE_TXT"

  # Druhá postpodmínka extrakce, opačný směr: promítl se zdroj do modelu?
  # Neblokuje — vynechaná preambule je legitimní, mělká extrakce ne, a rozdíl
  # mezi nimi pozná jen člověk nad reportem.
  echo "── Pokrytí zdroje ──────────────────────────────────"
  python3 "$S/coverage_check.py" --model "$MODEL" --source "$SOURCE_TXT"
fi

echo "── Projekce ────────────────────────────────────────"
python3 "$S/emit_word.py"    --model "$MODEL" --out "$OUT_DIR/$BASE.docx"
python3 "$S/emit_drawio.py"  --model "$MODEL" --out "$OUT_DIR/$BASE.drawio"
python3 "$S/emit_context.py" --model "$MODEL" \
        --out "$OUT_DIR/$BASE-kontext.md" --gaps "$OUT_DIR/$BASE-diry.md"

# Tvrzení pro kontrolu rozporů — jen když model nějaká nese.
if python3 -c "import sys,yaml; sys.exit(0 if (yaml.safe_load(open('$MODEL',encoding='utf-8')) or {}).get('claims') else 1)"; then
  python3 "$S/emit_claims.py" --model "$MODEL" --out "$OUT_DIR/$BASE-claims.json"
fi

# Prohlížeč jde poslední — čte adresář s artefakty, aby je mohl nabídnout.
VIEWER_ARGS=(--model "$MODEL" --out "$OUT_DIR/prohlizec.html" --outputs "$OUT_DIR")
if [[ -n "$SOURCE_TXT" ]]; then
  VIEWER_ARGS+=(--source "$SOURCE_TXT")
fi
python3 "$S/emit_viewer.py" "${VIEWER_ARGS[@]}"

echo "────────────────────────────────────────────────────"
echo "Hotovo. Výstupy v $OUT_DIR"
