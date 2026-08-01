# doc-to-model

Z hotového analytického dokumentu udělá **jednu validovanou strukturovanou pravdu**,
ze které se deterministicky generuje Word, diagram, kontext pro AI a **report děr** —
tedy seznam míst, kde původní dokument mlčí.

Není to sumarizátor. Chatbot vám dokument shrne; tenhle řetěz vám řekne, **co v něm není**
a **kde každé tvrzení stojí ve zdroji**.

## Proč

| Bez modelu | S modelem |
|---|---|
| Diagram a text se rozejdou | Obojí se generuje z týchž dat |
| Kontrola je názor | Akceptační kritérium je pole v modelu |
| Nevíte, co v dokumentu chybí | Model umí říct, kde sám nedrží |
| AI dostane přiložené PDF | AI dostane strukturovaná fakta s odkazy do zdroje |

**Kdy to nedělat:** u jednorázového dokumentu, ze kterého nic negenerujete. Napište ho rovnou.

## Instalace

Potřebujete Python 3.12 a [uv](https://docs.astral.sh/uv/) (nebo obyčejné `venv` + `pip`).

```bash
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -r requirements.txt
source .venv/bin/activate
```

## Zdrojové dokumenty

Adresář `inputs/` **není ve verzích** — jsou to cizí texty, ne naše práce, a repozitář
si je nedrží v kopii. Místo kopie je tu nástroj, kterým si je vyrobíte:

```bash
python3 utils/build-vyrez.py     # → inputs/aiact-pojisteni.md + .txt
```

Stáhne úřední české znění nařízení (EU) 2024/1689 z EUR-Lexu a složí z něj výřez
pro pojišťovnu: přílohu III bod 5 a navazující články o povinnostech zavádějícího
subjektu. Text přebírá doslova, včetně kazů úředního převodu — výřez, který se
tiše rozejde se zdrojem, je horší než žádný.

Z markdownu si ještě vyrobte text se záchytnými body, na který míří citace:

```bash
python3 scripts/ingest.py --in inputs/aiact-pojisteni.md --out inputs/aiact-pojisteni.txt
```

## Ověření, že to běží

```bash
bash scripts/build.sh model/aiact-pojisteni/aiact-pojisteni.yaml \
     model/aiact-pojisteni/out inputs/aiact-pojisteni.txt
```

Projde validace, ověří se opora tvrzení ve zdroji a vygeneruje se Word, diagram,
kontext, report děr a prohlížeč. Na přiloženém modelu má vyjít **27 z 27 výroků
s oporou** a **12 nálezů** v reportu děr. Prohlížeč (`out/prohlizec.html`) je
nejrychlejší způsob, jak pattern ukázat někomu, kdo ho nezná.

## Řetěz

```
0. VSTUP        → dokument + cíl                          člověk
1. INGEST       → dokument → text se záchytnými body      skript
2. SEGMENT      → návrh zdrojových míst                   skript
3. EXTRACT      → instance proti schématu, s citacemi     AI agent
4. VALIDATE     → struktura + reference                   skript · BRÁNA
5. GROUND-CHECK → má tvrzení oporu v citovaném místě      skript · BRÁNA
6. PROJECT      → Word, draw.io, kontext, díry, prohlížeč skript
7. REVIEW       → projít díry s autorem dokumentu         člověk · BRÁNA
```

**Na jazykovém modelu zůstává jediný krok — extrakce.** Všechno před ním i za ním
je skript, takže se to dá zkontrolovat. Krok 5 je postpodmínka extrakce: ověří, že
si model nevymyslel lhůtu, která v citovaném odstavci není.

Brány nedrží dobrá vůle, ale skripty. Každý krok zapíše výsledek a otisk modelu do
`<model>.state.json`; emitor nad neověřeným nebo mezitím změněným modelem odmítne běžet.

Plný popis včetně pravidel extrakce: [`.github/skills/doc-to-model/SKILL.md`](.github/skills/doc-to-model/SKILL.md).

## Použití s AI agentem

Repozitář je připravený jako **agent skill** — Copilot i Claude Code si instrukce
načtou samy:

| Kde | Co to je |
|---|---|
| `.github/skills/doc-to-model/SKILL.md` | Agent Skill (GitHub Copilot) |
| `.claude/skills/doc-to-model` | symlink na totéž (Claude Code) |
| `.github/copilot-instructions.md` | repo-wide kontext pro Copilot Chat i agenta |
| `AGENTS.md` | otevřený cross-vendor standard |

Stačí říct agentovi: *„vezmi `inputs/<dokument>` a udělej z něj model podle skillu
doc-to-model"*. Kroky 1–2 a 4–6 spustí jako skripty, krok 3 udělá sám.

## Struktura

```
schema/analytical-doc.linkml.yaml   schéma instance (LinkML)
scripts/                            ingest, segment, ground-check, emitory
lib/model_validate/                 sdílený validátor L1 (LinkML) + L2 (reference)
references/extraction.md            jak extrahovat věrně — pravidla, příklady, pasti
templates/model-skeleton.yaml       kostra instance k vyplnění
utils/build-vyrez.py                sestaví zdrojový výřez z EUR-Lexu
inputs/                             zdrojové dokumenty (neverzované)
model/<nazev>/                      instance + out/ s projekcemi
```

## Licence

Skripty a schéma: MIT. Zdrojové dokumenty v `inputs/` mají vlastní režim — texty
předpisů EU jsou veřejné, cokoli klientského sem nepatří.
