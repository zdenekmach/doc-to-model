#!/usr/bin/env bash
# Přegeneruj projekce jen z modelu — cesty si vezme ze `source_path` v něm.
#
#   bash rebuild.sh <model.yaml>
#
# Skutečná logika je ve skillu; tenhle soubor je ukazatel, stejně jako build.sh.
set -euo pipefail
exec bash "$(dirname "${BASH_SOURCE[0]}")/.github/skills/doc-to-model/scripts/rebuild.sh" "$@"
