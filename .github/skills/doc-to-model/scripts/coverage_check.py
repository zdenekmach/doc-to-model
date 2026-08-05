#!/usr/bin/env python3
"""coverage_check.py — promítly se všechny části zdroje do modelu?

Zrcadlo `ground_check.py`. Ten se ptá **„má výrok oporu ve zdroji?"** a chytá
vymyšlené požadavky. Tenhle se ptá opačně — **„promítla se věta ze zdroje do
nějakého výroku?"** — a chytá požadavky zapomenuté.

Obě chyby vyrábějí model, který vypadá spolehlivěji než dokument pod ním, ale
jen jedna z nich jde vidět na extrahovaných datech. Mělká extrakce projde
validací i kontrolou opory se samými jedničkami, protože to málo, co vytáhla,
je doložené. Proto ta druhá kontrola musí číst zdroj, ne model.

    python3 coverage_check.py --model model.yaml --source zdroj.txt [--json] [--strict]

Tři metriky, od nejhrubší po nejcennější:

1. **Nepokrytá místa** — segment zdroje, na který neukazuje žádný `source`.
   Levné a hrubé: kapitola citovaná jediným požadavkem se počítá jako pokrytá.
2. **Osiřelá čísla** — číslo ve zdroji, které není v žádném výroku. Lhůta,
   částka a počet jsou to nejdražší, co se dá při extrakci ztratit.
3. **Nepokryté normativní věty** — věta s „musí / nesmí / má právo…", jejíž
   slova se v žádném výroku neobjevila. Nejblíž tomu, na co se ptá člověk.
4. **Necitované zdroje** — místo, které model deklaroval a pak na něj neukázal
   žádným výrokem. Jediná binární metrika: ostatní tři stojí na překryvu slov,
   takže kapitolu, o které model jen mluví, započítají jako pokrytou. Tahle se
   ptá na doložitelnou vazbu a ošidit se nedá.

**Není to brána.** Legitimní extrakce běžně vynechá preambuli nebo přechodná
ustanovení, takže tvrdé blokování by lidi natlačilo na `--strict`-off a shodilo
i nálezy, které stojí za pohled. Report se čte, nezavírá cestu. `--strict`
existuje pro evals, kde je pokrytí regresní metrika.

Slovníky obou kontrol žijí v `lang/<kód>.yaml` a jazyk se detekuje ze zdroje
(viz `lang.py`). Hezká asymetrie uvnitř jednoho balíčku: „musí / může / budou"
jsou zároveň ve `stopwords` i v `normative_patterns`. Pro měření preciznosti
jsou to výplňová slova, protože nerozlišují. Pro měření pokrytí jsou to naopak
nejsilnější značky, protože označují větu, ze které požadavek plyne. Proto se
normativní věty hledají v syrovém textu, ne v kmenech.
"""
import argparse
import json
import re
import sys
from pathlib import Path

import yaml

import ground_check
import lang
from ground_check import OK_RATIO, requirement_text, stems
from pipeline_state import record, warn_if_missing
from segment import MD_RX, NUM_RX, PAGE_RX, dedupe, segment
from sourcemap import anchor_sources

# Věta kratší než tohle nemá dost rozlišovacích kmenů, aby se o jejím pokrytí
# dalo rozhodnout. Počítá se a hlásí, aby se přeskočení nedalo splést s nálezem.
MIN_STEMS = 3

# Normativní značky — věty, ze kterých v analytickém dokumentu plyne požadavek.
# Seznam je záměrně krátký a konzervativní: falešný nález v tomhle reportu stojí
# čtenáře důvěru rychleji než přehlédnutá věta, kterou stejně chytí metrika čísel.
# Značky normativní věty bydlí v `lang/<kód>.yaml`, ne tady. Regex napevno
# znamenal, že anglický dokument nahlásil „0 normativních vět" — a nula se čte
# jako „všechno pokryto", ne jako „neumím ten jazyk". Viz lang.py.


def load(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def is_heading(line: str) -> bool:
    """Nadpis, značka stránky nebo číslo kapitoly — ne obsah k pokrytí.

    Sdílí vzory se `segment.py`: co je pro segmentaci záchytný bod, není pro
    kontrolu pokrytí věta. Dvě kopie téhle úvahy by se rozešly a čísla kapitol
    by se začala hlásit jako osiřelá.
    """
    s = line.strip()
    return bool(PAGE_RX.match(s) or MD_RX.match(s) or (NUM_RX.match(s) and len(s) < 120))


def blocks(lines):
    """Zdroj → [(číslo prvního řádku, text odstavce)] bez nadpisů.

    Sousední řádky se slepí do odstavce, protože věta zalomená přes dva řádky by
    se jinak posuzovala po půlkách a obě půlky by vyšly jako nepokryté.
    """
    out, buf, start = [], [], None
    for i, raw in enumerate(lines):
        if not raw.strip() or is_heading(raw):
            if buf:
                out.append((start, " ".join(buf)))
                buf, start = [], None
            continue
        if start is None:
            start = i
        buf.append(raw.strip())
    if buf:
        out.append((start, " ".join(buf)))
    return out


def sentences(text: str):
    for part in re.split(r"(?<=[.!?])\s+", text):
        part = part.strip()
        if part:
            yield part


def model_vocabulary(m: dict):
    """Všechna slova a čísla, která se v modelu objevila jako výrok."""
    items = (list(m.get("claims") or [])
             + list(m.get("requirements") or [])
             + list(m.get("quality_requirements") or []))
    words, numbers = set(), set()
    for it in items:
        w, n = stems(requirement_text(it))
        words |= w
        numbers |= n
    return words, numbers, len(items)


def waived_ranges(lines, waivers):
    """Waiver → rozsah řádků odepsaného segmentu.

    Kotví se toutéž funkcí jako `Source.locator`, aby waiver nešel napsat ve
    tvaru, který zbytek pipeline neumí najít. Nezakotvený waiver se vrací
    zvlášť — tiše zahozený by vypadal jako splněný.
    """
    segs = dedupe(segment(lines))
    starts = [s[0] for s in segs]
    as_sources = {str(i): {"locator": w.get("locator", "")}
                  for i, w in enumerate(waivers)}
    anchors = anchor_sources(lines, as_sources)

    ranges, dangling = [], []
    for i, w in enumerate(waivers):
        a = anchors.get(str(i))
        if a is None:
            dangling.append(w)
            continue
        # Konec odepsaného úseku je začátek dalšího segmentu, ne konec souboru —
        # jinak by waiver na první kapitolu umlčel celý zbytek dokumentu.
        end = next((s for s in starts if s > a), len(lines))
        ranges.append((a, end, w))
    return ranges, dangling


def is_waived(line, ranges):
    return any(start <= line < end for start, end, _ in ranges)


def uncovered_places(lines, model_sources, waived):
    """Segmenty zdroje, do kterých neukazuje žádný `source` modelu."""
    segs = dedupe(segment(lines))
    if not segs:
        return [], 0, 0
    anchored = [a for a in anchor_sources(lines, model_sources).values() if a is not None]

    out, skipped = [], 0
    for idx, (line, loc, title, kind) in enumerate(segs):
        end = segs[idx + 1][0] if idx + 1 < len(segs) else len(lines)
        if any(line <= a < end for a in anchored):
            continue
        if is_waived(line, waived):
            skipped += 1
            continue
        out.append({"locator": loc, "title": title, "kind": kind, "line": line})
    return out, len(segs), skipped


def uncited_sources(m, lines, waived):
    """Zdroje deklarované v modelu, na které neukazuje žádný výrok.

    Nejtvrdší z metrik pokrytí a jediná binární. Ostatní stojí na překryvu slov,
    takže kapitolu, o které model jen mluví, započítají jako pokrytou. Tahle se
    ptá na doložitelnou vazbu: existuje výrok s `source: S12`?

    Zavést místo a necitovat ho je totéž jako odepsat ho — jen bez zapsaného
    důvodu. Naměřeno na reálném běhu: model s 69 zdroji citoval 33 z nich a
    ostatní metriky přitom hlásily 88% pokrytí.
    """
    src = {s["id"]: s for s in (m.get("sources") or []) if "id" in s}
    used = {
        it.get("source")
        for coll in ("claims", "requirements", "quality_requirements")
        for it in (m.get(coll) or [])
        if it.get("source")
    }
    anchors = anchor_sources(lines, src)

    out, skipped = [], 0
    for sid, meta in src.items():
        if sid in used:
            continue
        line = anchors.get(sid)
        if line is not None and is_waived(line, waived):
            skipped += 1
            continue
        out.append({"id": sid, "locator": meta.get("locator", ""),
                    "title": meta.get("title", ""), "line": line})
    return out, len(src), skipped


def orphan_numbers(bloks, model_numbers, waived):
    """Čísla ve zdroji, která se do žádného výroku nedostala."""
    out, skipped = [], 0
    for start, text in bloks:
        for sent in sentences(text):
            _, nums = stems(sent)
            missing = sorted(nums - model_numbers)
            if not missing:
                continue
            if is_waived(start, waived):
                skipped += 1
                continue
            out.append({"line": start, "numbers": missing, "sentence": sent})
    return out, skipped


def uncovered_norms(bloks, model_words, waived):
    """Normativní věty, jejichž slova se v žádném výroku neobjevila."""
    out, skipped, short, seen = [], 0, 0, 0
    for start, text in bloks:
        for sent in sentences(text):
            if not ground_check.active_pack().normative.search(sent):
                continue
            seen += 1
            words, _ = stems(sent)
            if len(words) < MIN_STEMS:
                short += 1
                continue
            ratio = len(words & model_words) / len(words)
            if ratio >= OK_RATIO:
                continue
            if is_waived(start, waived):
                skipped += 1
                continue
            out.append({"line": start, "ratio": round(ratio, 2), "sentence": sent})
    return out, short, skipped, seen


def coverage_stats(total_places, places, waived_places):
    """Pokryto ≠ odepsáno. Odepsané místo v modelu není a metrika to nesmí schovat.

    Kdyby se waiver počítal jako pokrytí, dala by se stovka vyrobit tím, že se
    dokument celý odepíše — a regresní metrika by měřila trpělivost s waivery.
    """
    covered = total_places - len(places) - waived_places
    pct = (covered / total_places * 100) if total_places else 100.0
    return covered, pct


def render(m, places, total_places, numbers, norms, short, statements,
           waived_places, waived_total, dangling, norms_seen, pack_note,
           uncited, total_sources):
    covered, pct = coverage_stats(total_places, places, waived_places)

    out = [f"# Pokrytí zdroje modelem — {m.get('title', '')}", ""]
    out.append("Ptá se opačně než kontrola opory: promítla se věta ze zdroje do")
    out.append("nějakého výroku? Chytá mělkou extrakci, kterou ostatní brány pustí.")
    out.append("")
    # Který jazykový balíček čísla vyrobil. Bez toho se nedá poznat, jestli
    # nula znamená „vše pokryto", nebo „hledalo se jinou abecedou".
    out.append(f"*Jazyk: {pack_note}*")
    out.append("")
    summary = f"**Místa:** {covered}/{total_places} pokryto ({pct:.0f} %)"
    if waived_places:
        summary += f" · **odepsáno:** {waived_places}"
    summary += (f" · **osiřelá čísla:** {len(numbers)} · "
                f"**nepokryté normativní věty:** {len(norms)} z {norms_seen} nalezených · "
                f"**necitované zdroje:** {len(uncited)} z {total_sources} · "
                f"**výroků v modelu:** {statements}")
    out.append(summary)
    out.append("")

    if dangling:
        out += ["## Waivery, které se nedají zakotvit", "",
                "Locator se ve zdroji nenašel — waiver nic neumlčuje a nálezy",
                "pod ním platí dál.", "",
                "| Locator | Důvod |", "|---------|-------|"]
        out += [f"| `{w.get('locator', '')}` | {w.get('reason', '')} |" for w in dangling]
        out.append("")

    if places:
        out += ["## Nepokrytá místa", "",
                "Segment zdroje, na který neukazuje žádný `source`.", "",
                "| Místo | Druh | Řádek |", "|-------|------|-------|"]
        out += [f"| {p['title']} (`{p['locator']}`) | {p['kind']} | {p['line']} |"
                for p in places]
        out.append("")

    if numbers:
        out += ["## Osiřelá čísla", "",
                "Číslo ve zdroji, které není v žádném výroku. Lhůta, částka nebo",
                "počet, které se ztratily při extrakci.", "",
                "| Čísla | Řádek | Věta |", "|-------|-------|------|"]
        out += [f"| {', '.join(n['numbers'])} | {n['line']} | {n['sentence'][:110]} |"
                for n in numbers]
        out.append("")

    if norms:
        out += ["## Nepokryté normativní věty", "",
                "Věta ukládá povinnost nebo právo, ale její slova se v žádném",
                "výroku neobjevila.", "",
                "| Shoda | Řádek | Věta |", "|-------|-------|------|"]
        out += [f"| {n['ratio']:.2f} | {n['line']} | {n['sentence'][:110]} |"
                for n in norms]
        out.append("")

    notes = []
    if waived_total:
        waivers = m.get("coverage_waivers") or []
        notes.append(f"{waived_total} nálezů umlčeno waiverem "
                     f"({len(waivers)} odepsaných míst)")
    if short:
        notes.append(f"{short} normativních vět kratších než {MIN_STEMS} "
                     "rozlišovací kmeny se neposuzovalo")
    if notes:
        out += ["_" + " · ".join(notes) + "._", ""]

    if waived_total:
        out += ["## Vědomě odepsaná místa", "",
                "| Locator | Důvod |", "|---------|-------|"]
        out += [f"| `{w.get('locator', '')}` | {w.get('reason', '')} |"
                for w in (m.get("coverage_waivers") or [])]
        out.append("")

    if not (places or numbers or norms):
        out += ["Nic neodepsaného nezbylo — každé místo zdroje má citaci, žádné",
                "číslo ani normativní věta nezůstaly mimo model.", ""]
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser(
        description="Ověř, že se všechny části zdroje promítly do modelu.")
    ap.add_argument("--model", required=True, type=Path)
    ap.add_argument("--source", required=True, type=Path, help="Zdrojový text (.md/.txt)")
    ap.add_argument("--out", type=Path, help="Report (default <model>-pokryti.md)")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--strict", action="store_true",
                    help="Skonči chybou, když něco zůstalo nepokryté (pro evals).")
    ap.add_argument("--lang", help="Kód jazykového balíčku (default: detekce ze zdroje).")
    args = ap.parse_args()

    if args.source.suffix.lower() == ".pdf":
        sys.exit("[CHYBA] --source čeká text. PDF si napřed vytáhni přes ingest.py.")

    m = load(args.model)
    warn_if_missing(args.model, "validate",
                    "pokrytí se počítá nad neověřeným modelem")

    raw = args.source.read_text(encoding="utf-8")
    pack, how = lang.resolve(raw, args.lang)
    ground_check.use_pack(pack)
    print(f"[jazyk] {how}")

    lines = raw.splitlines()
    model_sources = {s["id"]: s for s in (m.get("sources") or []) if "id" in s}
    words, numbers, statements = model_vocabulary(m)

    waived, dangling = waived_ranges(lines, m.get("coverage_waivers") or [])

    bloks = blocks(lines)
    places, total_places, w_places = uncovered_places(lines, model_sources, waived)
    orphans, w_nums = orphan_numbers(bloks, numbers, waived)
    norms, short, w_norms, norms_seen = uncovered_norms(bloks, words, waived)
    uncited, total_sources, w_uncited = uncited_sources(m, lines, waived)
    waived_total = w_places + w_nums + w_norms + w_uncited

    out = args.out or args.model.with_name(args.model.stem + "-pokryti.md")
    out.write_text(render(m, places, total_places, orphans, norms, short,
                          statements, w_places, waived_total, dangling,
                          norms_seen, how, uncited, total_sources),
                   encoding="utf-8")

    covered, pct = coverage_stats(total_places, places, w_places)
    findings = len(places) + len(orphans) + len(norms) + len(uncited)

    if args.json:
        print(json.dumps({
            "places": {"total": total_places, "covered": covered,
                       "waived": w_places, "uncovered": places},
            "orphan_numbers": orphans,
            "uncovered_norms": norms,
            "uncited_sources": uncited,
            "sources_total": total_sources,
            "waived": waived_total,
            "dangling_waivers": dangling,
            "skipped_short": short,
            "statements": statements,
        }, ensure_ascii=False, indent=2))
    else:
        waived_note = f" · odepsáno {w_places}" if w_places else ""
        print(f"[pokrytí] místa {covered}/{total_places} ({pct:.0f} %){waived_note} · "
              f"osiřelá čísla {len(orphans)} · "
              f"normativní věty {len(norms)}/{norms_seen} · "
              f"necitované zdroje {len(uncited)}/{total_sources} → {out}")
        for o in orphans[:5]:
            print(f"  ✗ číslo {', '.join(o['numbers'])}: {o['sentence'][:70]}")
        for n in norms[:5]:
            print(f"  ✗ nepokryto ({n['ratio']:.2f}): {n['sentence'][:70]}")
        if findings > 10:
            print(f"  … dalších {findings - 10} nálezů v reportu")
        # Umlčené nálezy se hlásí nahlas — waiver je rozhodnutí, ne ticho.
        if waived_total:
            print(f"  ({waived_total} nálezů umlčeno waiverem)")
        if short:
            print(f"  (neposuzováno {short} vět kratších než {MIN_STEMS} kmeny)")
        for w in dangling:
            print(f"  [POZOR] waiver '{w.get('locator', '')}' se ve zdroji nenašel "
                  "— neumlčuje nic", file=sys.stderr)

    record(args.model, "coverage-check", ok=(findings == 0 or not args.strict),
           detail={"places_total": total_places, "places_covered": covered,
                   "orphan_numbers": len(orphans), "uncovered_norms": len(norms),
                   "uncited_sources": len(uncited), "sources_total": total_sources,
                   "waived": waived_total, "dangling_waivers": len(dangling)})

    if findings and args.strict:
        sys.exit(f"\n[STRICT] {findings} neodepsaných nálezů pokrytí. Doplň model "
                 "o chybějící výroky, nebo místo odepiš přes `coverage_waivers` "
                 "s důvodem.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
