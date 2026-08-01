#!/usr/bin/env python3
"""sourcemap.py — mapování zdrojových míst (`Source.locator`) na řádky ve zdroji.

Sdílená jednotka. Volá ji `emit_viewer.py` (odskok z požadavku do textu) i
`ground-check.py` (ověření, že požadavek má oporu v citovaném místě). Dvě kopie
téhle logiky by se rozešly a odskok v prohlížeči by pak ukazoval jinam než
kontrola.
"""
import re

# Rozsah řádků, který se počítá jako „okolí" zdrojového místa, když není známý
# začátek dalšího zdroje.
DEFAULT_WINDOW = 60


def locator_patterns(locator: str):
    """Ze slovního locatoru („kap. 4", „s. 10–12", „§ 12") udělá vzory k hledání."""
    if not locator:
        return []
    # Text z PDF má rozházené mezery a zalomení uprostřed nadpisů. Doslovná
    # shoda by na tom padala, proto každý úsek bílých znaků odpovídá libovolnému
    # jinému — jinak by locator přepsaný z dokumentu nešel dohledat v jeho textu.
    flexible = r"\s+".join(re.escape(part) for part in locator.split())
    pats = [flexible]
    m = re.search(r"s\.\s*(\d+)", locator)
    if m:  # strana → značka z extrakce PDF
        pats.append(rf"===\s*STRANA\s+{m.group(1)}\s*===")
    m = re.search(r"kap\.\s*(\d+)", locator)
    if m:  # kapitola → markdown nadpis
        pats.append(rf"^#{{1,3}}\s*{m.group(1)}[.\s]")
    m = re.search(r"§\s*(\d+)", locator)
    if m:
        pats.append(rf"§\s*{m.group(1)}")
    return pats


def anchor_sources(lines, sources):
    """Zdroj → číslo řádku, na kterém jeho locator začíná (nebo None)."""
    anchors = {}
    for sid, src in sources.items():
        found = None
        for pat in locator_patterns(src.get("locator", "")):
            rx = re.compile(pat, re.IGNORECASE | re.MULTILINE)
            for i, line in enumerate(lines):
                if rx.search(line):
                    found = i
                    break
            if found is not None:
                break
        anchors[sid] = found
    return anchors


def source_windows(lines, anchors, window=DEFAULT_WINDOW):
    """Zdroj → (od, do) rozsah řádků.

    Konec je začátek dalšího zakotveného zdroje, jinak pevné okno. Tím se okolí
    nepřelije do sousední kapitoly a kontrola nezačne uznávat oporu, která patří
    jinam.
    """
    starts = sorted((v, k) for k, v in anchors.items() if v is not None)
    windows = {}
    for idx, (start, sid) in enumerate(starts):
        # Další HRANICE, ne další zdroj: víc zdrojů může ukazovat na stejný
        # řádek (např. „s. 8" a „s. 8–9"). Kdyby se bralo prostě následující,
        # okno by se scvrklo na jediný řádek a kontrola opory by hlásila
        # planý poplach.
        nxt = len(lines)
        for other_start, _ in starts[idx + 1:]:
            if other_start > start:
                nxt = other_start
                break
        end = min(nxt, start + window) if nxt - start > window else nxt
        windows[sid] = (start, max(end, start + 1))
    for sid, a in anchors.items():
        if a is None:
            windows[sid] = None
    return windows
