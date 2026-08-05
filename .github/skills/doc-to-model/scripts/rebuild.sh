#!/usr/bin/env bash
# rebuild.sh — přegeneruj všechny projekce jen z modelu.
#
#   bash rebuild.sh <model.yaml> [schema.linkml.yaml]
#
# Obálka nad `build.sh`, která si zbytek argumentů zjistí z modelu samotného:
# zdrojový text z `source_path`, výstupní adresář jako `<model>/out`. Model ví,
# odkud vznikl — není důvod to psát podruhé do příkazu.
#
# Proti `build.sh` je to úmyslně hloupější rozhraní: jeden argument, žádné
# poziční pasti (v build.sh se zdroj nedá předat bez výstupního adresáře a
# záměna obojího tiše vypne kontrolu opory). Kdo chce jiné cesty, ať sáhne
# rovnou po build.sh.
set -euo pipefail

MODEL="${1:?Použití: rebuild.sh <model.yaml> [schema.linkml.yaml]}"
shift    # co zbylo v "$@", je nepovinné schéma — jde dál beze změny
SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [[ ! -f "$MODEL" ]]; then
  echo "[CHYBA] Model neexistuje: $MODEL" >&2
  exit 2
fi

MODEL_DIR="$(cd "$(dirname "$MODEL")" && pwd)"

# Cestu čte parser YAMLu, ne grep — `source_path` může být v uvozovkách,
# ve složeném bloku i s dvojtečkou v hodnotě.
REL="$(python3 -c "
import sys, yaml
m = yaml.safe_load(open(sys.argv[1], encoding='utf-8')) or {}
print((m.get('source_path') or '').strip())
" "$MODEL")"

if [[ -z "$REL" ]]; then
  echo "[CHYBA] Model nemá vyplněné 'source_path' — nevím, odkud vznikl." >&2
  echo "" >&2
  echo "Doplň do hlavičky modelu cestu ke zdrojovému textu, relativně" >&2
  echo "k tomuhle souboru:" >&2
  echo "" >&2
  echo "  source_path: ../../inputs/zdroj.txt" >&2
  echo "" >&2
  echo "Nebo cesty vypiš ručně: bash build.sh <model> <out_dir> <zdroj.txt>" >&2
  exit 2
fi

# Cesta se srovná (`a/b/../c` → `a/c`), aby hlášky i logy ukazovaly místo,
# které jde rovnou zkopírovat do dalšího příkazu.
SOURCE="$(python3 -c "
import os, sys
print(os.path.normpath(os.path.join(sys.argv[1], sys.argv[2])))
" "$MODEL_DIR" "$REL")"

# Nenalezený zdroj se hlásí i s tím, co se z čeho odvodilo. Holé „soubor
# neexistuje" pošle člověka hledat překlep v příkazu, ve kterém žádná cesta
# není — obě si skript odvodil sám a musí ukázat obě.
if [[ ! -f "$SOURCE" ]]; then
  echo "[CHYBA] Zdrojový text z 'source_path' neexistuje." >&2
  echo "  model:        $MODEL" >&2
  echo "  source_path:  $REL   (relativně k adresáři modelu)" >&2
  echo "  hledáno v:    $SOURCE" >&2
  echo "" >&2
  echo "Buď oprav 'source_path' v modelu, nebo zdroj vrať na místo." >&2
  exit 2
fi

echo "── Odvozeno z modelu ───────────────────────────────"
echo "  zdroj:   $SOURCE"
echo "  výstupy: $MODEL_DIR/out"
echo ""

exec bash "$SKILL_DIR/scripts/build.sh" "$MODEL" "$MODEL_DIR/out" "$SOURCE" "$@"
