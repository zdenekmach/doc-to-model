#!/usr/bin/env python3
"""Sestaví výřez AI Actu relevantní pro pojišťovnu z úředního českého znění.

Výřez není ruční výtah — vzniká deterministicky z EUR-Lex HTML, takže se dá
kdykoli přegenerovat a ověřit proti zdroji. Tím je i sám ukázkou toho, o čem
je zbytek repozitáře.

    python3 utils/build-vyrez.py            # stáhne a sestaví
    python3 utils/build-vyrez.py --html X    # sestaví z už staženého HTML

Výstup: inputs/aiact-pojisteni.md
"""
from __future__ import annotations

import argparse
import html as htmllib
import pathlib
import re
import sys
import urllib.request

URL = "https://eur-lex.europa.eu/legal-content/CS/TXT/HTML/?uri=OJ:L_202401689"

# Co do výřezu patří a proč. Pořadí je pořadím ve výstupu.
RECITALS = [
    ("58", "Přístup k základním soukromým a veřejným službám"),
    ("96", "Proč se posuzuje dopad na základní práva"),
    ("158", "Finanční služby — vnitřní správa a řízení rizik"),
]
ARTICLES = ["4", "6", "13", "14", "26", "27", "50", "72"]
ANNEX_POINT = "5"  # Příloha III, bod 5 — písmeno c) je životní a zdravotní pojištění


def to_text(raw: str) -> list[str]:
    """HTML → řádky prostého textu se zachovanými odstavci."""
    body = raw.split("<body", 1)[-1]
    body = re.sub(r"(?is)<(script|style).*?</\1>", " ", body)
    body = re.sub(r"(?i)</(p|div|tr|h[1-6]|li|table)>", "\n", body)
    body = re.sub(r"(?i)<br\s*/?>", "\n", body)
    body = re.sub(r"(?s)<[^>]+>", "", body)
    txt = htmllib.unescape(body)
    txt = re.sub(r"[ \t\xa0]+", " ", txt)
    return [ln.strip() for ln in txt.splitlines()]


def reflow(chunk: list[str]) -> str:
    """Spojí osamocené odrážky (`a)`, `1.`) s textem, který k nim patří.

    V úředním HTML stojí značka odrážky na vlastním řádku. Bez slepení by
    každé písmeno vypadalo jako samostatný odstavec a citace by mířily na
    prázdno.
    """
    out: list[str] = []
    pending = ""
    for ln in chunk:
        if not ln:
            continue
        if re.fullmatch(r"[a-z]\)|\(\d+\)|\d+\.|[ivx]+\)", ln):
            pending = ln
            continue
        out.append(f"{pending} {ln}".strip() if pending else ln)
        pending = ""
    return "\n\n".join(out)


def slice_between(lines: list[str], start: int, stop_pat: str) -> list[str]:
    end = len(lines)
    for j in range(start + 1, len(lines)):
        if re.fullmatch(stop_pat, lines[j]):
            end = j
            break
    return lines[start:end]


def find_line(lines: list[str], pattern: str, start: int = 0) -> int:
    for i in range(start, len(lines)):
        if re.fullmatch(pattern, lines[i]):
            return i
    raise SystemExit(f"chyba: ve zdroji nenalezeno: {pattern}")


def build(lines: list[str]) -> str:
    parts: list[str] = [
        "# Výřez nařízení (EU) 2024/1689 — akt o umělé inteligenci",
        "",
        "Části relevantní pro pojišťovnu, která nasazuje AI do posuzování rizik "
        "a stanovování cen u životního a zdravotního pojištění.",
        "",
        "Zdroj: úřední české znění na EUR-Lex (`OJ:L_202401689`). Je to **výřez, "
        "ne úplné znění** — vybrané recitály, osm článků a bod 5 přílohy III. "
        "Sestaveno skriptem `utils/build-vyrez.py`, takže se dá přegenerovat "
        "a porovnat se zdrojem.",
        "",
        "Text je převzatý **doslova**, včetně drobných kazů úředního převodu do HTML "
        "(v nadpisu článku 72 je zdvojené „na trh“). Opravovat je by znamenalo, že se "
        "náš výřez rozejde se zdrojem — a přesně to tenhle repozitář nedělá.",
        "",
    ]

    for num, nazev in RECITALS:
        i = find_line(lines, rf"\({num}\)")
        chunk = slice_between(lines, i + 1, r"\(\d+\)")
        parts += [f"## Recitál {num} — {nazev}", "", reflow(chunk), ""]

    for num in ARTICLES:
        i = find_line(lines, rf"Článek {num}")
        # ODDÍL/KAPITOLA ukončuje článek stejně jako další článek — bez toho by
        # se do posledního článku oddílu přilepil nadpis toho následujícího.
        chunk = slice_between(
            lines, i + 1, r"Článek \d+|PŘÍLOHA [IVX]+|ODDÍL \d+|KAPITOLA [IVX]+"
        )
        nadpis = next((x for x in chunk if x), "")
        telo = reflow(chunk[chunk.index(nadpis) + 1:]) if nadpis else reflow(chunk)
        parts += [f"## Článek {num} — {nadpis}", "", telo, ""]

    a3 = find_line(lines, r"PŘÍLOHA III")
    # lines[a3+2] je podnadpis přílohy, který je totožný s naším nadpisem — vynechat.
    uvod = next((x for x in lines[a3 + 3: a3 + 8] if x), "")
    parts += [
        "## Příloha III — Vysoce rizikové systémy AI uvedené v čl. 6 odst. 2",
        "",
        uvod,
        "",
    ]
    b5 = find_line(lines, rf"{ANNEX_POINT}\.", a3)
    chunk = slice_between(lines, b5 + 1, r"\d+\.")
    parts += [f"### Příloha III, bod {ANNEX_POINT}", "", reflow(chunk), ""]

    return "\n".join(parts).replace("\n\n\n", "\n\n") + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--html", help="Už stažené EUR-Lex HTML (jinak se stáhne).")
    ap.add_argument("--out", default="inputs/aiact-pojisteni.md")
    args = ap.parse_args()

    if args.html:
        raw = pathlib.Path(args.html).read_text(encoding="utf-8")
    else:
        print(f"stahuji {URL}", file=sys.stderr)
        with urllib.request.urlopen(URL, timeout=120) as fh:
            raw = fh.read().decode("utf-8")

    out = pathlib.Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    text = build(to_text(raw))
    out.write_text(text, encoding="utf-8")

    slov = len(text.split())
    print(f"{out}: {len(text)} znaků, ~{slov} slov, ~{slov // 450 + 1} normostran")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
