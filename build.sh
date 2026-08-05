#!/usr/bin/env bash
# Zkratka, aby se řetěz dal spustit z kořene repozitáře.
#
#   bash build.sh <model.yaml> [out_dir] [zdroj.txt] [schema.yaml]
#
# Skutečná logika je ve skillu. Tenhle soubor je jen ukazatel, aby cesta
# k němu nemusela být v každém příkazu — skill se synchronizuje ze zdrojového
# systému a nemá smysl kvůli ergonomii sahat dovnitř.
set -euo pipefail
exec bash "$(dirname "${BASH_SOURCE[0]}")/.github/skills/doc-to-model/scripts/build.sh" "$@"
