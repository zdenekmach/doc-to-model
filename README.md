# doc-to-model

Vezme hotový analytický dokument — požadavkovou specifikaci, procesní analýzu,
výklad předpisu — a udělá z něj jednu validovanou datovou instanci. Z ní pak
deterministicky vypadne Word, diagram, kontext pro agenta a **report děr**.

Nejde o sumarizaci. Jde o to převést text na strukturu, kterou umí zkontrolovat
stroj, a ukázat, co v původním dokumentu chybí.

## Proč

Analytický dokument je špatná jednotka práce. Nedá se z něj ověřit, jestli si
neodporuje, jestli má každý požadavek akceptační kritérium, ani jestli se
diagram v příloze pořád shoduje s textem. Když se z něj udělá instance proti
schématu, jde všechno tohle zkontrolovat příkazem — a všechny výstupy se
generují z jednoho místa, takže se nemůžou rozejít.

Extrakce je jediný krok, který dělá jazykový model. Všechno před ní i za ní je
skript, a ta extrakce má **dvě postpodmínky, každou v opačném směru**:

| Kontrola | Ptá se | Chytá |
|----------|--------|-------|
| `ground_check.py` | má výrok oporu ve zdroji? (model → zdroj) | požadavek **vymyšlený** |
| `coverage_check.py` | promítla se věta zdroje do výroku? (zdroj → model) | požadavek **zapomenutý** |

Ta druhá je důležitější, než vypadá. Mělká extrakce projde validací i kontrolou
opory se samými jedničkami, protože to málo, co vytáhla, je doložené.

## Instalace

Potřeba je **Python 3.11 nebo novější** a pět balíčků z `requirements.txt`.
Zkratka přes celý řetěz (`build.sh`) je navíc bashový skript — na Windows tedy
Git Bash nebo WSL, nativní `cmd` ani PowerShell ho nespustí.

Nejdřív si ověř, jestli něco instalovat vůbec musíš.

Na macOS a Linuxu:

```bash
python3 -c "import yaml, docx, pypdf, linkml_runtime" && which linkml-validate
```

Na Windows totéž, ale příkazem `py -3`:

```bash
py -3 -c "import yaml, docx, pypdf, linkml_runtime" && which linkml-validate
```

Když oba příkazy projdou, máš hotovo a zbytek téhle sekce přeskoč.

> **Na Windows nepoužívej `python3`, a to nikde v tomhle repozitáři.**
> Instalátor z python.org registruje `python` a launcher `py`, nikoli `python3`.
> Windows navíc na `python3` váže zástupce Microsoft Store, takže se místo chyby
> otevře obchod — a to vypadá jako úplně jiný problém, než jaký nastal.
>
> Nepomůže ani virtuální prostředí: `venv` na Windows zakládá `python.exe`,
> `python3.exe` ne.
>
> Všude, kde je v příkazech `python3`, si tedy dosaď **`python`** (v aktivovaném
> `.venv`) nebo **`py -3`** (bez něj).

### macOS

Python 3.11+ bývá po ruce; když ne, `brew install python@3.12` nebo instalátor
z python.org.

```bash
git clone https://github.com/zdenekmach/doc-to-model.git
cd doc-to-model
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

### Windows

Python z python.org nebo z Microsoft Store; při instalaci nech zaškrtnuté
**Add python.exe to PATH**. Git Bash přijde s [Git for Windows](https://gitforwindows.org).

V Git Bash:

```bash
git clone https://github.com/zdenekmach/doc-to-model.git
cd doc-to-model
py -3 -m venv .venv && source .venv/Scripts/activate
pip install -r requirements.txt
```

Dva rozdíly proti macOS: Python se volá `py -3` (viz poznámka výše), a aktivace
vede přes `Scripts`, ne `bin`.

Po aktivaci prostředí už `python` míří dovnitř `.venv` a chová se stejně jako
na macOS — rozdíl se týká jen příkazů, které pouštíš předtím.

### Ověření

S aktivovaným prostředím platí obojí stejně:

```bash
linkml-validate --help     # strukturální validace; bez něj se přeskočí a řekne to nahlas
python -m pytest .github/skills/doc-to-model/scripts/ -q    # 16 testů; potřebuje pytest
```

Virtuální prostředí je doporučení, ne podmínka. Když balíčky nainstaluješ
globálně, funguje to taky — `.venv` jen drží verze stranou od zbytku systému.
Bez něj ale na Windows zůstaň u `py -3` místo `python`.

## Spuštění z GitHub Copilot CLI

Copilot CLI hledá skilly mimo jiné v `.claude/skills`, což je přesně tam, kde
tenhle leží. Nic se nikam nekopíruje.

```bash
npm install -g @github/copilot     # Node 22+, aktivní Copilot předplatné
cd doc-to-model
copilot
```

V session se přihlas přes `/login` a zkontroluj, že skill vidí:

```
/skills list
/skills info doc-to-model
```

Pak stačí říct, co chceš:

```
Vezmi dokument specifikace.pdf a udělej z něj model podle skillu doc-to-model.
```

Skript v skillu neběží sám od sebe — Copilot se u shellových příkazů ptá na
potvrzení. To je správně; předschvalovat `shell` má smysl až u skillu, kterému
plně důvěřuješ.

## Spuštění z Claude Code

Stejná složka, žádná úprava:

```bash
cd doc-to-model
claude
```

Skill se aktivuje sám podle popisu ve frontmatteru, nebo si ho vyžádej jménem.

## Spuštění bez agenta

Extrakci musí udělat člověk nebo model, zbytek řetězu je skript. Když už model
máš, druhá polovina je jeden příkaz:

```bash
bash build.sh model/<jméno>/model.yaml out inputs/zdroj.txt
```

Projde validací, oběma kontrolami a vygeneruje všechny projekce. Bez třetího
argumentu se kontroly přeskočí a emitory to vypíšou jako varování.

Když jde jen o přegenerování hotového modelu, stačí model:

```bash
bash rebuild.sh model/<jméno>/model.yaml
```

Zdroj si vezme ze `source_path` v modelu, výstupy dá do `<model>/out`. Proto
stojí za to verzovat jen `model.yaml` a zdrojový text — zbytek se vyrobí znovu
a vyjde bajtově stejně (Word až na časové razítko v ZIP obalu).

Jednotlivé kroky umí `--help`:

```bash
python3 .github/skills/doc-to-model/scripts/ingest.py --help
python3 .github/skills/doc-to-model/scripts/coverage_check.py --help
```

## Co je uvnitř

Repozitář má **dvě části a záměrně je nemíchá**.

```
.github/skills/doc-to-model/   ← SYNCHRONIZOVANÉ ze zdrojového systému
  SKILL.md                     postup, brány mezi kroky, anti-vzory
  schema/                      LinkML schéma instance
  scripts/                     ingest, segmentace, kontroly, emitory
  scripts/validate/            validátor L1+L2 (vendorovaný)
  lang/                        jazykové balíčky kontrol
  references/extraction.md     jak extrahovat věrně
  templates/                   kostra instance k vyplnění

.claude/skills/doc-to-model    symlink na výše — jedno místo, dvě cesty

AGENTS.md · README.md · build.sh · rebuild.sh · requirements.txt · utils/ · tools/
                               ← VLASTNÍ, tady se udržují
```

Ta hranice není kosmetická. Všechno pod `.github/skills/doc-to-model/` se
přepisuje synchronizací a ruční úpravy tam nepřežijí — patří do zdrojového
systému, nebo do transformací v `tools/adapt.py`. Zbytek repozitáře je jeho
vlastní a synchronizace se ho nedotkne.

Pořadí kroků nedrží žádný wrapper — vynucují ho samotné skripty přes
`<model>.state.json` s otiskem modelu. Emitor nad neověřeným nebo mezitím
změněným modelem odmítne běžet.

## Schéma

Modelovací jazyk je [LinkML](https://linkml.io). Validace má dvě vrstvy:
**L1** strukturální dělá `linkml-validate` (enumy, povinná pole, typy,
kardinalita), **L2** referenční je vlastní (unikátnost id, visící odkazy mezi
prvky) — to LinkML sám neřeší.

Vlastní schéma jde podstrčit čtvrtým argumentem `build.sh`. Emitory vypíšou i
kolekce, které `analytical-doc` nezná, místo aby je tiše zahodily.

## Původ

Skill vznikl jako součást většího osobního systému a tohle je jeho samostatný
výřez. Nenese s sebou sousední nástroje na návrh schématu, plnění modelu
z researche ani kontrolu rozporů. Emitor tvrzení (`emit_claims.py`) tu zůstal
schválně — jeho `*-claims.json` je vstup pro takovou kontrolu, ať už ji pustíš
čímkoli.

Aktualizace skillu ze zdrojového systému: `tools/sync-from-personalskills.sh`.
Přenese jen synchronizovanou část, odpojí ji od okolí (`tools/adapt.py`) a ověří,
že po ní nezbyla žádná vazba na systém, ze kterého přišla.

`utils/build-vyrez.py` sestaví výřez AI Actu pro pojišťovnictví přímo z EUR-Lexu.
Výřez tedy není ruční výtah — dá se přegenerovat a ověřit proti zdroji, což je
zároveň ukázka toho, o čem je zbytek repozitáře.

## Licence

MIT — viz [LICENSE](LICENSE). Repo neobsahuje kód třetích stran, takže tě
neváže žádná další atribuce.
