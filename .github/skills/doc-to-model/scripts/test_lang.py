#!/usr/bin/env python3
"""Testy jazykových balíčků.

Hlídají hlavně jednu věc: přesun konstant do YAML nesmí změnit VÝZNAM. Při
prvním pokusu se ztratily hranice slova kolem skládané skupiny a `zajist[íi]`
začalo chytat i „nezajistí" — počet nálezů na témže vstupu vyskočil z 1 na 4.
Nespadlo nic, jen se tiše posunula čísla. Přesně to, co se hledá zpětně nejhůř.

    python3 -m pytest scripts/test_lang.py -q
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import lang  # noqa: E402


@pytest.fixture(scope="module")
def packs():
    return lang.load_packs()


def test_zabudovane_balicky_existuji(packs):
    assert "cs" in packs and "en" in packs


def test_kazdy_balicek_ma_provenienci(packs):
    for code, p in packs.items():
        assert p.source in ("builtin", "generated"), f"{code}: neznámý source '{p.source}'"


def test_normativni_regex_ma_hranice_slova(packs):
    """Regrese: bez \\b kolem skupiny chytá vzor i uvnitř jiného slova."""
    cs = packs["cs"]
    assert cs.normative.search("Zaměstnavatel zajistí přenos.")
    assert not cs.normative.search("Zaměstnavatel nezajistí přenos."), \
        "chytá zápor jako normativní větu — zmizely hranice slova"


def test_anglicke_znacky_chytaji_should_a_shall(packs):
    en = packs["en"]
    for veta in (
        "Undertakings should document the approach.",
        "The provider shall keep the logs.",
        "Undertakings need to define roles.",
    ):
        assert en.normative.search(veta), veta


def test_cesky_regex_nechyta_anglickou_vetu(packs):
    assert not packs["cs"].normative.search("Undertakings should document the approach.")


def test_detekce_rozlisi_jazyky(packs):
    cs_text = "Zaměstnavatel musí podle tohoto zákona zajistit, aby byly údaje předány."
    en_text = "The undertaking should ensure that the data are processed in accordance with this Regulation."
    assert lang.detect(cs_text, packs)[0].code == "cs"
    assert lang.detect(en_text, packs)[0].code == "en"


def test_neznamy_jazyk_nevrati_balicek(packs):
    # Finština — žádný balíček ji nemá, takže nesmí nic „skoro sednout".
    fi = ("Vakuutusyhtiön on varmistettava, että tietojen käsittely tapahtuu "
          "tämän asetuksen mukaisesti ja että valvontaviranomainen saa tiedot.")
    pack, ranking = lang.detect(fi, packs)
    assert pack is None, f"neznámý jazyk prošel jako {pack}"
    assert ranking, "žebříček musí být i při neúspěchu — bez něj se práh nedá ladit"


def test_prazdny_text_nespadne(packs):
    assert lang.detect("", packs)[0] is None


def test_balicek_bez_stopwordu_je_chyba():
    with pytest.raises(ValueError):
        lang.LanguagePack({"code": "xx", "normative_patterns": ["musí"]}, Path("xx.yaml"))


def test_balicek_bez_znacek_je_chyba():
    with pytest.raises(ValueError):
        lang.LanguagePack({"code": "xx", "stopwords": ["a"]}, Path("xx.yaml"))
