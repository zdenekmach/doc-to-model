#!/usr/bin/env python3
"""Testy obálky `rebuild.sh` — hlavně toho, jak selhává.

Obálka odvozuje cesty, které nejsou v příkazu vidět. Když se netrefí, musí
ukázat obojí: co četla z modelu a kam to složila. Holé „soubor neexistuje"
posílá člověka hledat překlep v příkazu, ve kterém žádná cesta není.

    python3 -m pytest scripts/test_rebuild.py -q
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REBUILD = Path(__file__).resolve().parent / "rebuild.sh"


def run(*args):
    return subprocess.run(["bash", str(REBUILD), *map(str, args)],
                          capture_output=True, text=True)


def model(tmp_path: Path, telo: str) -> Path:
    p = tmp_path / "model.yaml"
    p.write_text(telo, encoding="utf-8")
    return p


def test_chybejici_model_konci_jasne(tmp_path):
    r = run(tmp_path / "neni.yaml")
    assert r.returncode == 2
    assert "Model neexistuje" in r.stderr


def test_bez_source_path_rekne_co_doplnit(tmp_path):
    r = run(model(tmp_path, "id: X\ntitle: Y\n"))
    assert r.returncode == 2
    assert "source_path" in r.stderr
    # Rada musí být proveditelná: ukázat tvar zápisu i únikovou cestu.
    assert "source_path:" in r.stderr and "build.sh" in r.stderr


def test_nenalezeny_zdroj_ukaze_obe_cesty(tmp_path):
    r = run(model(tmp_path, "id: X\ntitle: Y\nsource_path: ../pryc/zdroj.txt\n"))
    assert r.returncode == 2
    assert "../pryc/zdroj.txt" in r.stderr, "chybí hodnota z modelu"
    assert "hledáno v:" in r.stderr, "chybí odvozená absolutní cesta"


def test_prazdne_source_path_je_totez_co_chybejici(tmp_path):
    """`source_path: ` projde schématem, ale cesta to není."""
    r = run(model(tmp_path, "id: X\ntitle: Y\nsource_path: '   '\n"))
    assert r.returncode == 2
    assert "nemá vyplněné" in r.stderr


def test_schema_zna_source_path():
    """Bez slotu ve schématu by model se `source_path` neprošel validací."""
    yaml = pytest.importorskip("yaml")
    s = Path(__file__).resolve().parent.parent / "schema" / "analytical-doc.linkml.yaml"
    doc = yaml.safe_load(s.read_text(encoding="utf-8"))
    sloty = doc["classes"]["Document"]["attributes"]
    assert "source_path" in sloty
    assert "source_document" in sloty, "cesta nenahrazuje lidský název"


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
