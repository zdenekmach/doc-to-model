#!/usr/bin/env python3
"""Jazykové balíčky pro postpodmínky extrakce — data, ne konstanty v kódu.

Obě kontroly (`ground_check`, `coverage_check`) potřebují vědět, která slova
jsou v daném jazyce výplň a která věta je normativní. Dokud to byly konstanty
v kódu, dokument v jiném jazyce **tiše prošel**: STOP list nic neodfiltroval,
takže se shoda nafoukla, a regex nenašel ani jednu normativní větu, takže
report napsal „0" tam, kde měl napsat „neumím ten jazyk".

Balíček je YAML v `lang/<kód>.yaml`. Přidat jazyk znamená přidat soubor.

DETEKCE VYRŮSTÁ ZE STEJNÝCH DAT. Každý balíček se oskóruje proti textu podle
svých vlastních stopwordů; vyhrává nejvyšší zásah na tisíc slov. Žádná další
závislost a hlavně: data, která řídí kontroly, řídí i výběr, takže se nemůžou
rozejít. Detektor natrénovaný jinde by tuhle vlastnost neměl.

Když ani jeden balíček nepřekročí práh, je to **nález, ne detail**. Volající
smí buď skončit s chybou, nebo si balíček doplnit (skill k tomu vede agenta),
ale nikdy ne mlčky pokračovat s cizím jazykem.

CLI:
    python3 lang.py detect <soubor>     # co bys na tomhle textu použil a proč
    python3 lang.py list                # dostupné balíčky
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml

LANG_DIR = Path(__file__).resolve().parent.parent / "lang"

# Pod tímhle zásahem na tisíc slov už to není jazyk, ale náhoda. Kalibrováno
# na dvou reálných vstupech: AI Act cs 85/1000 (en 2), EIOPA opinion en 182/1000
# (cs 0). Odstup mezi správným a cizím balíčkem je řádový, takže práh nemusí být
# vymazlený — má oddělit „rozumím" od „nerozumím", ne dva blízké jazyky.
MIN_HITS_PER_1K = 8.0


class LanguagePack:
    def __init__(self, data: dict, path: Path):
        self.path = path
        self.code: str = data["code"]
        self.name: str = data.get("name", data["code"])
        self.source: str = data.get("source", "unknown")
        self.stopwords: set[str] = {w.lower() for w in (data.get("stopwords") or [])}
        patterns = data.get("normative_patterns") or []
        # Hranice slova kolem CELÉ skupiny, přesně jak to měl původní zabudovaný
        # regex. Bez nich `zajist[íi]` chytí i „nezajistí" a české počty vyskočí
        # (naměřeno: 1 → 4 nepokrytých vět na témže vstupu). Skládání ze seznamu
        # nesmí měnit význam, jen místo, kde je seznam uložený.
        self.normative = (
            re.compile(r"\b(" + "|".join(patterns) + r")\b", re.IGNORECASE)
            if patterns else None
        )
        if not self.stopwords:
            raise ValueError(f"{path.name}: prázdný seznam stopwords")
        if self.normative is None:
            raise ValueError(f"{path.name}: prázdný seznam normative_patterns")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<LanguagePack {self.code} ({self.source})>"


def load_packs() -> dict[str, LanguagePack]:
    packs: dict[str, LanguagePack] = {}
    if not LANG_DIR.is_dir():
        return packs
    for p in sorted(LANG_DIR.glob("*.yaml")):
        with open(p, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        pack = LanguagePack(data, p)
        packs[pack.code] = pack
    return packs


def _words(text: str) -> list[str]:
    return re.findall(r"[^\W\d_]+", (text or "").lower())


def score(text: str, pack: LanguagePack) -> float:
    """Zásahy stopwordů na tisíc slov."""
    words = _words(text)
    if not words:
        return 0.0
    hits = sum(1 for w in words if w in pack.stopwords)
    return hits * 1000.0 / len(words)


def detect(text: str, packs: dict[str, LanguagePack] | None = None):
    """Vrať (pack_nebo_None, žebříček). Žebříček je vždy, i když nic nevyhrálo."""
    packs = packs if packs is not None else load_packs()
    ranking = sorted(
        ((code, score(text, p)) for code, p in packs.items()),
        key=lambda kv: kv[1],
        reverse=True,
    )
    if not ranking or ranking[0][1] < MIN_HITS_PER_1K:
        return None, ranking
    return packs[ranking[0][0]], ranking


def format_ranking(ranking) -> str:
    return " · ".join(f"{code} {sc:.0f}/1000" for code, sc in ranking) or "žádné balíčky"


def resolve(text: str, override: str | None = None):
    """Balíček pro tenhle text. Vrací (pack, popis_volby).

    `override` obchází detekci — ale jen na existující balíček. Vymyslet si kód
    jazyka, který nemáme, není volba, je to překlep.
    """
    packs = load_packs()
    if not packs:
        raise SystemExit(f"[jazyk] žádné balíčky v {LANG_DIR} — instalace je neúplná")

    if override:
        if override not in packs:
            raise SystemExit(
                f"[jazyk] balíček '{override}' neexistuje. Dostupné: {', '.join(sorted(packs))}.\n"
                f"        Nový se přidá souborem {LANG_DIR}/{override}.yaml"
            )
        pack = packs[override]
        return pack, f"zvoleno ručně: {pack.code} ({pack.source})"

    pack, ranking = detect(text, packs)
    if pack is None:
        raise SystemExit(
            "[jazyk] NEROZPOZNÁNO — žádný balíček nepřekročil práh "
            f"{MIN_HITS_PER_1K:.0f} zásahů/1000 slov.\n"
            f"        Naměřeno: {format_ranking(ranking)}\n"
            f"        Kontrola by na cizím jazyce vrátila čísla, která nic neznamenají.\n"
            f"        Buď vyber balíček přes --lang, nebo přidej {LANG_DIR}/<kód>.yaml\n"
            f"        (stopwords + normative_patterns, source: generated)."
        )
    return pack, f"detekováno: {pack.code} ({pack.source}) — {format_ranking(ranking)}"


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    cmd = sys.argv[1]

    if cmd == "list":
        packs = load_packs()
        if not packs:
            print(f"žádné balíčky v {LANG_DIR}")
            return 1
        for code, p in sorted(packs.items()):
            print(f"  {code:<4} {p.name:<12} {p.source:<10} "
                  f"{len(p.stopwords):>3} stopwordů  {p.path.name}")
        return 0

    if cmd == "detect":
        if len(sys.argv) < 3:
            print("použití: lang.py detect <soubor>")
            return 2
        text = Path(sys.argv[2]).read_text(encoding="utf-8")
        pack, ranking = detect(text)
        print(f"  žebříček: {format_ranking(ranking)}")
        if pack is None:
            print(f"  → NEROZPOZNÁNO (práh {MIN_HITS_PER_1K:.0f}/1000)")
            return 1
        print(f"  → {pack.code} ({pack.name}, source: {pack.source})")
        return 0

    print(f"neznámý příkaz: {cmd}")
    return 2


if __name__ == "__main__":
    sys.exit(main())
