# AGENTS.md

Postup, kterým se v tomhle repozitáři dělá z dokumentu model, je ve skillu
`.github/skills/doc-to-model/SKILL.md`. **Ten je zdrojem pravdy — přečti si ho
dřív, než začneš.**

Tenhle soubor je rozcestník a čtyři pravidla. Existuje proto, že skill se načítá,
až když si ho agent vybere; tohle platí i tehdy, když si ho nevybere.

```
ingest → segment → EXTRACT (ty) → validate → ground-check → coverage → project → review
```

Tvůj jediný krok je **extrakce**. Zbytek jsou skripty a mají brány: emitor nad
neověřeným modelem odmítne běžet, takže pořadí nejde obejít.

## Čtyři pravidla

1. **Nic, co ve zdroji není, se nesmí objevit jako fakt.** Doplněné prvky dostanou
   `confidence: assumed` a patří do reportu děr. Vyplněný model vypadá lépe, a právě
   proto je domýšlení mezer tichá fabrikace.
2. **Chybějící akceptační kritérium je nález, ne mezera k vyplnění.** Nedoplňuj ho.
3. **`locator` je doslovný řetězec z dokumentu.** Nadpis přesně jak stojí, „§ 12",
   „s. 7". Skládaná cesta `Kapitola / Podkapitola` v dokumentu není, takže se nenajde —
   pak se nedá ověřit žádný výrok a odskok do zdroje nefunguje nikde.
4. **Nula si zaslouží druhý pohled.** Report děr bez nálezu, nula normativních vět,
   nula tvrzení předaných do kontroly rozporů. U reálného dokumentu to obvykle
   znamená, že něco neproběhlo, ne že je všechno v pořádku.

Plné znění pravidel extrakce s příklady:
`.github/skills/doc-to-model/references/extraction.md`.

## Prostředí

Potřeba je Python 3.11+ a balíčky z `requirements.txt`. Ověř si to takhle:

```bash
python3 -c "import yaml, docx, pypdf, linkml_runtime" && which linkml-validate
```

Když to projde, nic dalšího nezařizuj — balíčky už v systému jsou.

Když to spadne, doinstaluj je. Virtuální prostředí je doporučení, ne podmínka;
`.venv` v repozitáři být nemusí a jeho aktivace bez něj skončí chybou.

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

**Na Windows nahraď `python3` za `py -3`** (nebo za `python`, když už běžíš
v aktivovaném `.venv`). `python3` tam neexistuje ani v prostředí — Windows na
ten název váže zástupce Microsoft Store, takže se místo chyby otevře obchod.
Aktivace vede přes `.venv/Scripts/activate`, ne `bin`. A `build.sh` je bashový
skript, takže potřebuje Git Bash nebo WSL.

Spouštěj z kořene repozitáře. Celý řetěz za extrakcí jedním příkazem:

```bash
bash build.sh model/<jméno>/model.yaml out inputs/<zdroj>.txt
```
