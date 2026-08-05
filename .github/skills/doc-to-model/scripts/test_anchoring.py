#!/usr/bin/env python3
"""Testy zakotvení locatorů a brány, která na něm stojí.

Reálný případ (2026-08-05): model postavený agentem měl locatory ve tvaru
„Results / A sparse annotation layer", zatímco dokument nese jen
„### A sparse annotation layer". Skládaná cesta se nikdy nenajde. Zakotvilo se
6 z 22 míst, všech 20 výroků dostalo „nezakotveno" — a přesto z toho vznikl
Word, diagram i prohlížeč, protože „nezakotveno" bylo jen slabý nález.

    python3 -m pytest scripts/test_anchoring.py -q
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from sourcemap import anchor_sources, source_windows  # noqa: E402

ZDROJ = """# Titulek dokumentu

## Results

### A sparse annotation layer

Text první podkapitoly.

### Root cause

Text druhé podkapitoly.

## Discussion

Text diskuse.
""".splitlines()


def _anchors(*locators):
    src = {f"S{i}": {"locator": loc} for i, loc in enumerate(locators, 1)}
    return anchor_sources(ZDROJ, src)


def test_doslovny_nadpis_se_zakotvi():
    a = _anchors("A sparse annotation layer")
    assert a["S1"] is not None


def test_skladana_cesta_se_nezakotvi():
    """Jádro nálezu: `Rodič / Dítě` v dokumentu není, takže se nenajde."""
    a = _anchors("Results / A sparse annotation layer")
    assert a["S1"] is None


def test_dopsana_glosa_v_zavorce_se_nezakotvi():
    a = _anchors("Discussion (limitations section)")
    assert a["S1"] is None
    assert _anchors("Discussion")["S1"] is not None


def test_rozdilne_mezery_nevadi():
    """Text z PDF má rozsypané mezery — na tom kotvení padat nesmí."""
    a = _anchors("A  sparse   annotation\tlayer")
    assert a["S1"] is not None


def test_okno_konci_dalsim_zakotvenym_mistem():
    """Sourozenci se nesmí přelít do sebe, jinak by opora uznala cizí text."""
    src = {
        "S1": {"locator": "A sparse annotation layer"},
        "S2": {"locator": "Root cause"},
    }
    a = anchor_sources(ZDROJ, src)
    w = source_windows(ZDROJ, a)
    od1, do1 = w["S1"]
    assert do1 <= a["S2"], "okno prvního místa zasahuje do druhého"


def test_prah_brany_je_definovany():
    import ground_check
    assert 0.0 < ground_check.ANCHOR_MIN_RATIO <= 1.0


def test_necitovany_zdroj_se_najde():
    """Zdroj deklarovaný a nepoužitý žádným výrokem je nález.

    Ostatní metriky pokrytí stojí na překryvu slov, takže tenhle případ pustí.
    Reálně: model s 69 zdroji citoval 33 a pokrytí přitom hlásilo 88 %.
    """
    import coverage_check

    m = {
        "sources": [
            {"id": "S1", "locator": "A sparse annotation layer"},
            {"id": "S2", "locator": "Root cause"},
        ],
        "requirements": [{"id": "FR-01", "title": "X", "source": "S1"}],
    }
    uncited, total, skipped = coverage_check.uncited_sources(m, ZDROJ, [])
    assert total == 2
    assert [u["id"] for u in uncited] == ["S2"]
    assert skipped == 0


def test_deklarovany_necitovany_zdroj_misto_nepokryva():
    """Jádro nálezu 2026-08-05: pokrytí se nesmí dát vyrobit opsáním segmentace.

    Reálně: model se 76 zdroji a 14 výroky hlásil 100 % pokrytí — víc než běh
    se 105 výroky (80 %), protože opsal víc segmentů a citoval míň.
    """
    import coverage_check

    zdroje = {
        "S1": {"locator": "A sparse annotation layer"},
        "S2": {"locator": "Root cause"},
        "S3": {"locator": "Discussion"},
    }
    places, total, _ = coverage_check.uncovered_places(ZDROJ, zdroje, [], {"S1"})
    nepokryte = {p["title"] for p in places}
    assert "Root cause" in nepokryte and "Discussion" in nepokryte
    assert "A sparse annotation layer" not in nepokryte

    vse = coverage_check.uncovered_places(ZDROJ, zdroje, [], set(zdroje))
    assert len(vse[0]) < len(places), "citace všech zdrojů musí pokrytí zvýšit"
    assert vse[1] == total


def test_cited_source_ids_bere_vsechny_kolekce():
    import coverage_check

    m = {
        "claims": [{"source": "S1"}],
        "requirements": [{"source": "S2"}, {"title": "bez zdroje"}],
        "quality_requirements": [{"source": "S3"}],
    }
    assert coverage_check.cited_source_ids(m) == {"S1", "S2", "S3"}


def test_stav_rozlisi_neproběhlo_od_neproslo(tmp_path):
    """„Neproběhlo" a „proběhlo a neprošlo" vedou k jiné radě pro člověka."""
    import pipeline_state

    model = tmp_path / "model.yaml"
    model.write_text("id: x\n", encoding="utf-8")

    assert pipeline_state.status(model, "coverage-check") == "missing"
    pipeline_state.record(model, "coverage-check", ok=False)
    assert pipeline_state.status(model, "coverage-check") == "failed"
    pipeline_state.record(model, "coverage-check", ok=True)
    assert pipeline_state.status(model, "coverage-check") == "ok"

    model.write_text("id: y\n", encoding="utf-8")
    assert pipeline_state.status(model, "coverage-check") == "missing"


def test_vsechny_zdroje_citovane_neni_nalez():
    import coverage_check

    m = {
        "sources": [{"id": "S1", "locator": "Root cause"}],
        "claims": [{"id": "T1", "title": "X", "source": "S1"}],
    }
    uncited, total, _ = coverage_check.uncited_sources(m, ZDROJ, [])
    assert total == 1 and uncited == []
