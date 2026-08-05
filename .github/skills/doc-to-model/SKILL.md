---
name: doc-to-model
license: MIT
description: "Triggers: /doc-to-model, 'udělej ze specifikace strukturovanou pravdu', 'převeď dokument na SSOT', 'z dokumentu vytáhni model', 'document to single source of truth', 'analytický dokument na data', 'z toho dokumentu vygeneruj diagram a word'. Vezme EXISTUJÍCÍ analytický dokument (specifikace, procesní analýza, výklad předpisu, zadání změny) a udělá z něj jednu validovanou instanci strukturované pravdy, ze které deterministicky emituje Word, draw.io diagram, kontext pro AI a report děr. NENÍ to research o doméně (→ /domain-model) ani návrh schématu (→ /data-metamodel) ani těžba dokumentu do učebních rámců (→ /extract)."
---

# Doc → Model — z hotového dokumentu strukturovaná pravda

**Verze:** 1.13.0 | **Pattern:** INGEST → SEGMENT → EXTRACT → VALIDATE → GROUND-CHECK → COVERAGE → PROJECT (substrát strukturované pravdy)

Chybějící vstupní operace substrátu. `domain-model` plní instanci z **researche**,
`data-metamodel` navrhuje **schéma**. Tenhle skill plní instanci z **jednoho konkrétního
dokumentu, který už existuje** — a hned ukáže, co v něm chybí.

Job: *„Mám analytický dokument. Chci z něj jeden zdroj pravdy, ze kterého se vygeneruje
dokument i diagram, který se dá zkontrolovat, a který se stane kontextem pro AI."*

---

## Proč to stojí za to

Dokument je pro člověka čitelný a pro stroj neprůhledný. Jakmile z něj vznikne model,
platí čtyři věci naráz:

1. **Diagram a text se nemůžou rozejít** — obojí se generuje z týchž dat.
2. **Kontrola přestane být názorem** — akceptační kritérium je pole v modelu, ne dojem.
3. **Model umí říct, kde sám nedrží** — požadavek bez zdroje, bez akceptace, domyšlený.
4. **AI dostane kontext, který se dá ověřit** — místo přiloženého PDF strukturovaná fakta
   s odkazy do zdroje.

Rozhodovací hrana (kdy pattern nepoužít) je v `.claude/docs/DATA-PROJECTION-PATTERN.md`.
U jednorázového dokumentu, ze kterého nic negeneruješ, to nedělej.

---

## Workflow

**Tenhle skill je orchestrátor.** Kroky nespouští žádný wrapper — sekvenci drží
tenhle dokument a **vynucují ji samotné skripty**. Každý krok zapíše výsledek do
`<model>.state.json` spolu s otiskem modelu; následující krok si předpoklad ověří
a nad neověřeným nebo mezitím změněným modelem odmítne běžet. Druhý orchestrátor
(shell wrapper, který by pořadí popisoval znovu) by se s tímhle dokumentem rozešel.

```
0. VSTUP        → dokument + cíl                          člověk
1. INGEST       → dokument → text se záchytnými body      skript
2. SEGMENT      → návrh zdrojových míst (`sources`)       skript
3. EXTRACT      → instance proti schématu, s citacemi     TY (agent)  ←──┐
4. VALIDATE     → struktura + reference                   skript · BRÁNA │
5. GROUND-CHECK → má výrok oporu v citovaném místě        skript · BRÁNA │
6. COVERAGE     → promítl se zdroj do modelu              skript ────────┘
7. PROJECT      → Word, draw.io, kontext, díry, prohlížeč skript      doplnění
8. REVIEW       → projít díry s autorem dokumentu         člověk · BRÁNA
```

Jediný krok, který zůstává na jazykovém modelu, je **EXTRACT**. Všechno před ním
i za ním je skript. Extrakce má **dvě postpodmínky, každou v jiném směru**:

| Krok | Ptá se | Chytá |
|------|--------|-------|
| 5 GROUND-CHECK | má výrok oporu ve zdroji? (model → zdroj) | požadavek **vymyšlený** |
| 6 COVERAGE | promítla se věta zdroje do výroku? (zdroj → model) | požadavek **zapomenutý** |

Obě chyby vyrábějí model, který vypadá spolehlivěji než dokument pod ním. Jen
jedna z nich jde vidět na extrahovaných datech — proto ta druhá kontrola čte
zdroj, ne model. Mělká extrakce projde validací i kontrolou opory se samými
jedničkami, protože to málo, co vytáhla, je doložené.

`scripts/build.sh` spouští **jen kroky 4–7** a potřebuje **hotový model**. Není
to spouštěč celého řetězu a samotný dokument mu nestačí.

### Jak řetěz projet

**Dostaneš dokument a projdeš kroky popořadě sám, bez ptaní mezi nimi.**
O výsledku každého kroku podej krátkou zprávu a pokračuj.

Konkrétně, od dokumentu k výstupům:

```bash
# 1. INGEST — jen když vstup NENÍ text (.pdf, .docx). U .txt a .md přeskoč.
python3 scripts/ingest.py --in <dokument> --out inputs/zdroj.txt

# 2. SEGMENT — návrh VŠECH zdrojových míst; nezkracuj ho
python3 scripts/segment.py --source inputs/zdroj.txt --out /tmp/sources.yaml

# 3. EXTRACT — TADY PÍŠEŠ MODEL TY. Žádný skript to neudělá.
#    Vznikne <cíl>/model.yaml: sources + requirements + claims proti schématu.

# 4.–7. Zbytek jedním příkazem, až model EXISTUJE a něco obsahuje
bash scripts/build.sh <cíl>/model.yaml <cíl>/out inputs/zdroj.txt
```

<gate severity="BLOCKER">
**Nezačínej `build.sh`.** Je to poslední krok, ne první. Když ho spustíš nad
neexistujícím modelem, skončí chybou; když nad prázdným, doběhne a vyrobí
prázdné výstupy. Ani jedno není výsledek.

Reálně se stalo obojí: jednou agent přeskočil EXTRACT a dostal prázdný Word,
podruhé spustil rovnou `build.sh` a dostal „model file not found".
</gate>

Ptát se před každým krokem k ničemu nepomáhá. Bezpečnost drží **brány, ne
otázky**: validace blokuje, emitor nad neověřeným modelem odmítne běžet,
nezakotvené locatory běh zastaví. Když je něco špatně, řetěz spadne sám a
řekne proč. Souhlas s krokem, který by stejně selhal, ničemu nepomůže.

Zastav se jen ve třech případech:

| Kdy | Co udělat |
|-----|-----------|
| Krok 0 — nevíš, **co má vzniknout** nebo **kam to uložit** | zeptej se, obojí jednou větou |
| Brána spadla | ohlas naměřenou hodnotu a příčinu, neobcházej ji `--warn-only` bez souhlasu |
| Krok 8 REVIEW | předej report děr člověku; tohle je jeho práce, ne tvoje |

Ostatní rozhodnutí uděláš sám.

**Výchozí záměr je vymodelovat celý dokument.** Zdrojová místa nezkracuj a
nevynechávej části zdroje, dokud ti člověk neřekne, že chce jen výřez.

<gate severity="BLOCKER">
**Krok 3 EXTRACT nesmíš přeskočit ani delegovat.** Bez něj vznikne model bez
jediného požadavku a tvrzení — a řetěz za ním doběhne, protože validovat a
promítat se dá i prázdno. Vypadne Word bez obsahu a pokrytí kolem patnácti
procent, což vypadá jako výsledek, ale výsledek to není.

Reálně se to stalo: agent přečetl v tomhle kroku větu o tom, kdo extrakci dělá,
usoudil, že na ni nemá nárok, a přeskočil ji. Extrakce je tvoje práce, ať v téhle
session běží kterýkoli model.
</gate>

Když člověk výslovně řekne, že chce po některém kroku zastavit, poslechni.
Výchozí stav je ale průběh bez přerušení.

### 0. Vstup

Zeptej se na dvě věci, pokud nejsou zřejmé: **který dokument** a **co z něj má vzniknout**
(dokument, diagram, kontrola konzistence, kontext pro agenta — může být víc).

Cílový adresář zvol vedle zdrojového dokumentu, například `model/<nazev>/`.
Model, jeho stav a výstupy patří k sobě.

Zdrojový dokument ulož nebo odkaž — model bez dohledatelného zdroje je k ničemu.

### 1. INGEST — dokument na text

```bash
python3 scripts/ingest.py --in dokument.pdf --out inputs/zdroj.txt
```

Umí `.pdf`, `.docx`, `.md`, `.txt`. Zachovává záchytné body: u PDF hranice stran
(`=== STRANA N ===`), u Wordu nadpisy jako markdown. Bez nich by se dalo citovat
jen na dokument jako celek.

Skenované PDF bez textové vrstvy pozná podle mizivého výtěžku a řekne to nahlas.
Takový vstup potřebuje OCR — tichý prázdný výstup by byl horší než chyba.

### 2. SEGMENT — návrh zdrojových míst

```bash
python3 scripts/segment.py --source inputs/zdroj.txt --out /tmp/sources.yaml
```

Najde stránky, nadpisy, číslované i římské kapitoly a paragrafy, a vypíše hotový
blok `sources:` k vložení do modelu. **Navrhne jich všechna** — výchozí záměr je
modelovat celý dokument.

<gate severity="BLOCKER">
**Nezkracuj `sources`, pokud ti to člověk výslovně neřekl.**

Kolik zdrojových míst zavedeš, tolik je **strop pokrytí** modelu. Výrok se nemá
kam odkázat, tak nevznikne. Vztah je skoro mechanický, naměřeno na témž
dokumentu o 76 místech:

| Zavedeno `sources` | Strop | Skutečné pokrytí |
|---:|---:|---:|
| 65 | 86 % | 80 % |
| 18 | 24 % | 21 % |

Zkrácení se tedy neprojeví jako „úspornější model", ale jako **mělká extrakce**.
A ta projde validací i kontrolou opory se samými jedničkami, protože to málo, co
vytáhla, je doložené. Pozná ji až kontrola pokrytí — tedy až na konci, kdy je
práce hotová.

Výřez dělej jen tehdy, když padne věta typu „zajímá mě jen kapitola 4". Pak
`--max` nebo ruční výběr, a skript ti rovnou spočítá, na jaký strop jsi šel.
</gate>

Skript si své návrhy sám zkusí dohledat toutéž funkcí, kterou pak používá
prohlížeč i kontrola opory, a nahlásí poměr. Locator, který se nedá zakotvit,
by byl jen ozdoba u citace.

<gate severity="BLOCKER">
`locator` je **doslovný řetězec z dokumentu** — nadpis přesně jak stojí, „§ 12",
„s. 7". Hledá se jako text, takže co v dokumentu není, se nenajde.

Nevymýšlej strukturu, kterou zdroj nemá:

| Nefunguje | Funguje |
|-----------|---------|
| `Results / A sparse annotation layer` | `A sparse annotation layer` |
| `Discussion (limitations section)` | `Discussion` |
| `Materials and Methods / Data` | `Data` |

Skládaná cesta „rodič / dítě" vypadá pořádněji, ale v dokumentu není. Reálný
případ: 16 z 22 locatorů se nezakotvilo, všech 20 výroků dostalo „nezakotveno"
a odskok v prohlížeči nefungoval. Po odříznutí předpon zakotvilo 22 z 22.

Duplicitní nadpis není problém — okno zdroje končí začátkem dalšího
zakotveného místa, takže sourozenci se nepřelijí do sebe.
</gate>

### 3. EXTRACT — naplnění instance

**Tohle děláš ty, ne skript.** Extrakce je jediný krok řetězu, který nejde
naprogramovat — čte se dokument a rozhoduje se, co je v něm požadavek a co
tvrzení. Nedeleguj ji nikam ven a nevolej kvůli ní žádné API; probíhá v téhle
session, ať v ní běží kterýkoli model.

Schéma: `schema/analytical-doc.linkml.yaml`. Vyplň jen sekce, které zdroj opravdu
obsahuje — prázdná sekce je poctivější než vymyšlená.

Pravidla extrakce (detail a příklady: `references/extraction.md`):

| Pravidlo | Proč |
|----------|------|
| Rozliš tvrzení od požadavku (*co se má stát × jak to je*) | Jeden dokument nese obojí; viz sekce Dva typy výroků |
| Každý výrok dostane `source` — odkaz do `sources` | Bez toho model nejde ověřit proti zdroji |
| `confidence: explicit / derived / assumed` u každého výroku | Odliší, co je ve zdroji, od toho, cos domyslel |
| Co ve zdroji není, jde do `open_questions`, ne do požadavků | Model nesmí tvrdit víc než dokument |
| `acceptance` piš jen tehdy, když zdroj kritérium má | Chybějící akceptace je nález, ne mezera k vyplnění |
| Procesní kroky pojmenuj slovesem | Diagram pak dává smysl bez legendy |

<gate severity="BLOCKER">
Nic, co ve zdroji není, se nesmí objevit jako fakt. Doplněné prvky mají
`confidence: assumed` a patří do reportu děr.
</gate>

### 4. VALIDATE

```bash
python3 scripts/validate/validate.py \
  --schema schema/analytical-doc.linkml.yaml \
  --data model.yaml --class Document
```

L1 (struktura, enumy, typy) a L2 (unikátnost id, viset nesmí žádná reference) blokují.
Po úspěchu zapiš krok do stavu, jinak emitory odmítnou běžet:

```bash
python3 scripts/mark_step.py --model model.yaml --step validate
```

Pro sémantické rozpory mezi tvrzeními navaž `/doc-consistency` — tenhle skill vyrábí
vstup, který je pro ni ideální, protože je typovaný.

### 5. GROUND-CHECK — má tvrzení oporu ve zdroji?

```bash
python3 scripts/ground_check.py --model model.yaml --source zdroj.txt
```

Postpodmínka extrakce. Pro každý požadavek ověří, že jeho vlastní slova a čísla
se vyskytují v okolí místa, na které se odkazuje. Není to kontrola správnosti —
chytá hrubší a nebezpečnější případ: **tvrzení, které v citovaném místě nemá oporu
vůbec.** Přesně tak vzniká model, který vypadá spolehlivěji než dokument pod ním.

Čeština se ohýbá, proto se porovnávají kmeny slov. **Čísla se porovnávají přesně**
a mají zvláštní váhu: když požadavek nese lhůtu, částku nebo počet a ani jedno
číslo není v citovaném místě, verdikt je „bez opory" bez ohledu na slovní shodu.
Vymyšlená lhůta je nejtypičtější a nejdražší chyba extrakce.

| Verdikt | Co s tím |
|---------|----------|
| opora | v pořádku |
| slabá opora · bez zdroje | projít okem |
| **bez opory · visící odkaz** | **blokuje** — oprav extrakci |

Kromě verdiktů se hlásí **zakotvenost zdrojů** a ta má vlastní bránu: když se
ve zdroji najde míň než polovina locatorů, běh skončí. Nezakotvený locator není
slabý důkaz, je to **žádný** — výrok se nedá ověřit a v prohlížeči neodskočí,
přitom model navenek vypadá trasovatelně. Do 2026-08-05 to byl jen slabý nález,
takže model, kde ani jeden z 20 výroků nešel ověřit, prošel a vyrobil Word i web.

Poměr se vypisuje vždycky, i když je v pořádku — bez naměřené hodnoty v logu se
nepozná rozdíl mezi „locatory sedí" a „nikdo je neměřil".

Planý poplach se odbaví `--warn-only`, ale ne mlčky: report `<model>-opora.md`
zůstává a je v něm vidět, co se přeskočilo.

<gate severity="BLOCKER">
Nespouštěj emitory, dokud ground-check neprošel — pokud existuje zdrojový text.
Bez něj emitory poběží, ale nahlas upozorní, že výstup nemá ověřenou oporu.
</gate>

### 6. COVERAGE — promítl se zdroj do modelu?

```bash
python3 scripts/coverage_check.py --model model.yaml --source zdroj.txt
```

Druhá postpodmínka extrakce, opačným směrem než kontrola opory. Tři metriky
od nejhrubší po nejcennější:

| Metrika | Co hlásí |
|---------|----------|
| Nepokrytá místa | segment zdroje, na který neukazuje žádný `source` |
| **Osiřelá čísla** | číslo ve zdroji, které není v žádném výroku |
| Nepokryté normativní věty | věta s „musí / nesmí / má právo", jejíž slova v modelu nejsou |

Osiřelá čísla jsou nejsilnější signál. Lhůta, částka a počet jsou to nejdražší,
co se dá při extrakci ztratit, a zároveň to, co se očima kontroluje nejhůř.

#### Jazyk zdroje

Obě kontroly potřebují vědět, která slova jsou v daném jazyce výplň a čím se
pozná normativní věta. Bydlí to v `lang/<kód>.yaml`, ne v kódu — přidat jazyk
znamená přidat soubor.

Jazyk se **detekuje ze zdroje**: každý balíček se oskóruje podle svých vlastních
stopwordů a vyhraje nejvyšší zásah na tisíc slov. Volbu i naměřený žebříček
vypíše běh a nese ji i report. `--lang <kód>` detekci obejde.

<gate severity="BLOCKER">
Když žádný balíček nepřekročí práh, kontrola **skončí chybou**. Nedopočítávej
ji ručně a nevydávej její čísla dál — na cizí jazyk se stopwordy nechytnou,
takže shoda se nafoukne a normativních vět se najde nula. Nula se čte jako
„všechno pokryto", ne jako „neumím ten jazyk".
</gate>

Když na neznámý jazyk narazíš, **založ balíček** `lang/<kód>.yaml`:

```yaml
code: de
name: Deutsch
source: generated     # POVINNĚ, když balíček vzniká za běhu
stopwords: [der, die, das, und, ist, ...]        # výplňová slova, ~40 stačí
normative_patterns: ['muss', 'darf\s+nicht', 'ist\s+verpflichtet', ...]
```

`source: generated` znamená „vymyslel to model, nikdo to neověřil" a report to
u čísel vypíše. Balíček, který někdo prošel, přepiš na `builtin`. Bez toho
rozlišení si za tři měsíce nebudeš jistý, čemu ta čísla odpovídají.

Hranice slova doplňuje loader kolem celé skupiny sám — do vzorů je nepiš.

**Neblokuje.** Preambule, definice pojmů nebo přechodná ustanovení zůstávají
nepokryté zcela legitimně, takže tvrdá brána by lidi natlačila na vypínač a
shodila i nálezy, které stojí za pohled. `--strict` existuje pro evals.

#### Doplňovací smyčka

Nález znamená vrátit se k extrakci — ale **cíleně, ne novým průchodem**. Report
pojmenuje locator, číslo řádku i konkrétní větu, takže se přidávají výroky pro
konkrétní místa. Opakovaná extrakce celého dokumentu by přečíslovala id a
zahodila ruční opravy z kroku 8.

Smyčka končí na **úsudku, ne na procentu**. Sto procent je špatný cíl: kdyby se
honilo číslo, extrakce si začne vymýšlet požadavky, aby metriku nasytila — a to
je přímý útok na hlavní slib skillu z kroku 3. Každý nález se proto buď
doextrahuje, nebo vědomě odepíše:

```yaml
coverage_waivers:
  - locator: "1. Úvodní ustanovení"
    reason: "Preambule, neplyne z ní požadavek."
```

Odepisuje se celý segment — umlčí nálezy napříč všemi třemi metrikami. `reason`
je povinný, protože waiver bez důvodu je tichý souhlas s mělkou extrakcí. Waiver,
jehož locator se ve zdroji nedá zakotvit, se hlásí a neumlčuje nic.

Dva doplňovací průchody stačí. Když ani po nich pokrytí nedává smysl, problém
není v extrakci, ale ve volbě dokumentu nebo schématu.

<gate severity="WARNING">
Pokrytí pod polovinou míst u dokumentu, který má být modelován celý, znamená
mělkou extrakci — ne hotový model. Odepsat zbytek waiverem jde, ale důvod bude
muset obstát před autorem dokumentu v kroku 8.
</gate>

### 7. PROJECT

```bash
bash scripts/build.sh model.yaml [out_dir] [zdroj.txt]
```

Validace běží první a při chybě se render nespustí.

| Emitor | Výstup | K čemu |
|--------|--------|--------|
| `emit_word.py` | `.docx` | dokument pro člověka, sekce jen ty, které model má |
| `emit_drawio.py` | `.drawio` | editovatelný diagram; `--swimlanes` rozloží kroky podle aktéra |
| `emit_context.py` | `-kontext.md` | kompaktní kontext pro AI/agenta |
| `emit_context.py --gaps` | `-diry.md` | kde model nedrží — hlavní přínos |
| `emit_claims.py` | `-claims.json` | tvrzení pro deterministickou kontrolu rozporů |
| `emit_viewer.py` | `prohlizec.html` | tři panely: zdroj · model · výstupy, s odskokem do zdroje |

**Prohlížeč** je nejlepší způsob, jak pattern ukázat někomu, kdo ho nezná: vlevo
původní text, uprostřed co se z něj vytáhlo, vpravo co se z toho vygenerovalo.
Kliknutí na požadavek zvýrazní místo ve zdroji, ze kterého pochází. Odskok se
dohledává podle pole `locator` — kolik zdrojů se podařilo zakotvit, vypíše skript
i samotná stránka, takže se nedá splést domněnka s ověřenou stopou.

Zdrojový text předej jako třetí argument (`.md` / `.txt`; PDF si napřed vytáhni).
Bez něj se prohlížeč vygeneruje také, jen bez levého panelu.

### 8. REVIEW

Report děr projdi s autorem dokumentu. Není to seznam chyb extrakce, je to seznam
míst, kde původní dokument mlčí. To bývá cennější než vygenerovaný Word.

---

## Dva typy výroků — tvrzení a požadavek

Analytický dokument nese dva druhy vět a **oba se běžně potkají v jednom
dokumentu**. „ČNB je regulátorem pro oblast XY" není požadavek a nikdy jím
nebude, přesto je to nosný fakt, ze kterého požadavky teprve plynou.

Rozlišení proto sedí **na výroku, ne na dokumentu**. Model má dvě oddělené
kolekce a obě mohou být neprázdné zároveň.

| | `claims` — tvrzení | `requirements` — požadavek |
|---|---|---|
| Odpovídá na | jak to je | co se má stát |
| Vlastní pole | `claim_type`, `basis`, **`subject`, `predicate`, `value`, `scope`** | `priority`, `acceptance`, `actor` |
| Společné | `id`, `title`, `description`, `source`, `confidence` (třída `Statement`) | totéž |

Ta čtveřice `subject` · `predicate` · `value` · `scope` je celek, ne výběr.
Rozkládá tvrzení na části, které umí porovnat stroj — bez ní tvrzení do kontroly
rozporů nedojde, protože není co s čím porovnat.

| Věta ze zdroje | subject | predicate | value | scope |
|----------------|---------|-----------|-------|-------|
| „Anotace nese 612 lokusů miRNA." | anotace miRNA | počet lokusů | 612 | Ensembl Protists 59 |
| „Hlášení se odesílá do 20. dne." | měsíční hlášení | lhůta odeslání | 20. den následujícího měsíce | JMHZ |
| „Rodinnou homologií se potvrdí 46–48 %." | pozitivní kontrola | míra potvrzení | 46–48 % | C. elegans, A. thaliana |

`scope` je povinný proto, že chrání před falešným poplachem: 30 dnů u jednoho
rozsahu a 90 u jiného není rozpor.

**Rozhodovací otázka při extrakci:** *říká ta věta, co se má stát, nebo jak to je?*
Normativní věta je požadavek, popisná je tvrzení. Když to nejde rozhodnout, volí se
tvrzení a otázka jde do `open_questions` — model nemá předstírat povinnost, kterou
zdroj neuložil.

`claim_type` rozlišuje, jakou míru ověřitelnosti od výroku čekat: **fakt** se dá
dohledat, **výklad** je něčí čtení, **predikce** se ověřit nedá vůbec, **definice**
zavádí pojem.

### Co se čím řídí

| Část | Chování |
|------|---------|
| `ingest`, `segment`, `sourcemap`, validace | na typu výroku nezávislé |
| `ground_check` | ověřuje obojí stejně; na tvrzeních bývá shoda vyšší (0,91–1,00), protože jsou zdroji jazykově blíž než přeformulovaný požadavek |
| Report děr | **pravidla se větví podle typu výroku** — u tvrzení se nehledá akceptační kritérium, u požadavku se nehledá opora |
| Word, kontext, prohlížeč | oddělené sekce, každá jen když není prázdná |
| `emit_drawio` | bez procesu se přeskočí — analýza ani výklad sled kroků popisovat nemusí |
| „Chybí proces" jako díra | hlásí se jen v modelu, který něco požaduje |

Pravidla pro tvrzení: chybí opora (`basis`), chybí zdroj, tvrzení označené jako
`assumed` nebo `derived`, a **predikce vydávaná za doložený fakt** (`claim_type:
predikce` s `confidence: explicit` — budoucnost nemůže být ve zdroji doslova).

### Proč to děláme — vazba `justified_by`

Požadavek smí ukázat na tvrzení, ze kterých plyne. Tím model odpovídá na otázku,
kterou volný text v popisu nikdy nezodpoví ověřitelně: **proč ten požadavek vůbec
existuje.** Odůvodnění je pak samo dohledatelné, protože tvrzení nese zdroj
i míru jistoty.

```yaml
requirements:
  - id: FR-01
    title: "Sledovat legislativní roadmapu konkurence"
    justified_by:
      - T-04        # Tlak na konsolidaci poroste
```

Visící odkaz zachytí referenční kontrola (L2) a validace selže. Report děr přidá
nález **požadavek bez odůvodnění** — ale jen v modelu, kde odůvodnění někdo
skutečně používá. Kdyby pravidlo platilo vždy, zaplavilo by modely, kde vazba
nedává smysl, a svádělo by k vymýšlení odůvodnění pro forma.

### Kontrola rozporů — předání do `/doc-consistency`

Tvrzení rozložená na `subject`, `predicate`, `value` a `scope` jsou přesně to, co
potřebuje deterministická vrstva kontroly rozporů: stejný subjekt a predikát ve
stejném rozsahu s jinou hodnotou je tvrdý rozpor. `emit_claims.py` je to rozhraní.

```bash
python3 scripts/emit_claims.py --model model.yaml --out out/claims.json
python3 11-Client-Projects/generali-beanz/kompilator/check.py out/claims.json
```

Smysl není ušetřit práci, ale **nemít dvě verze pravdy**. Kdyby kontrola rozporů
extrahovala tvrzení sama, porovnávala by jiná tvrzení, než jaká jsou v dokumentu
a v diagramu.

Tvrzení bez `subject`, `predicate` nebo `value` se vynechají — bez nich není co
porovnat. Kolik jich vypadlo, skript řekne nahlas; tichý výpadek by kazil statistiku.

### Vlastní schéma

Čtvrtý argument `build.sh` je cesta ke schématu. Emitory vypisují sekce podle
toho, **co je v instanci**, ne podle pevného seznamu — kolekce, kterou
`analytical-doc` nezná, se v kontextu vypíše obecně místo aby se tiše zahodila.

Když ti `analytical-doc` nesedí, navrhni vlastní schéma přes `/data-metamodel`
a pusť na něj tytéž skripty. Validátor, kontrola opory i prohlížeč jsou na
konkrétních názvech tříd nezávislé.

### Filtr v prohlížeči

Když model nese oba typy výroků, dostane prohlížeč přepínač **Vše · Jen tvrzení ·
Jen požadavky · Neověřené**. Poslední volba nechá jen to, co je `assumed` nebo
`derived` — nejrychlejší způsob, jak někomu ukázat, co je doložené a co domyšlené.

Měřeno na testovacím modelu: dřív byly 4 nálezy z 6 planý poplach, po větvení
pravidel **nula z šesti**.

## Gates

<gate severity="BLOCKER">
Validace prochází (L1+L2) dřív, než se cokoli vyrenderuje. Vynucují skripty,
ne dobrá vůle — bez zápisu do `<model>.state.json` emitor skončí chybou.
</gate>

<gate severity="BLOCKER">
Změna modelu po validaci zneplatní stav (otisk souboru). Emitovat z modelu,
který se od ověření pohnul, nejde.
</gate>

<gate severity="BLOCKER">
Každý požadavek má `source`, nebo je uveden v reportu děr. Netrasovatelný model
je horší než původní dokument, protože vypadá spolehlivěji.
</gate>

<gate severity="WARNING">
Report děr, který nic nenašel, u reálného dokumentu znamená spíš mělkou extrakci
než dokonalý zdroj.
</gate>

---

## Anti-vzory

| Anti-vzor | Místo toho |
|-----------|------------|
| Doplnit chybějící akceptační kritérium, ať model vypadá úplně | Nechat prázdné a vykázat v dírách |
| Extrahovat všechno, protože to jde | Extrahovat to, z čeho se něco emituje |
| Vzít mělkou extrakci jako hotovou, protože opora vyšla 100 % | Přečíst pokrytí — věrnost je podmínka nutná, ne postačující |
| Napsat locator jako cestu `Kapitola / Podkapitola` | Doslovný řetězec z dokumentu — cesta se nikdy nenajde |
| Odepsat zbytek zdroje waiverem, ať metrika sedí | Waiver má důvod, který obstojí před autorem dokumentu |
| Ručně dopsat do Wordu, co v modelu chybí | Doplnit model a přegenerovat |
| Použít na jednorázový dokument | Napsat ho rovnou |

---

## Reference

| Soubor | Obsah |
|--------|-------|
| `schema/analytical-doc.linkml.yaml` | Schéma instance |
| `scripts/ingest.py` | Dokument (PDF/Word/text) → text se záchytnými body |
| `scripts/segment.py` | Návrh zdrojových míst + self-check zakotvitelnosti |
| `scripts/ground_check.py` | Postpodmínka extrakce — opora tvrzení ve zdroji (model → zdroj) |
| `scripts/coverage_check.py` | Postpodmínka extrakce — pokrytí zdroje modelem (zdroj → model) |
| `scripts/pipeline_state.py` · `mark_step.py` | Brány mezi kroky (`<model>.state.json`) |
| `scripts/sourcemap.py` | Locator → řádky; sdílí prohlížeč i kontrola opory |
| `scripts/lang.py` · `lang/*.yaml` | Jazykové balíčky — stopwordy a normativní značky jako data |
| `scripts/build.sh` | Zkratka pro kroky 4–7 (validace → opora → pokrytí → projekce) |
| `scripts/emit_word.py` · `emit_drawio.py` · `emit_context.py` · `emit_viewer.py` · `emit_claims.py` | Emitory |
| `references/extraction.md` | Jak extrahovat věrně (pravidla, příklady, pasti) |
| `scripts/validate/` | Validátor (L1 linkml-validate, L2 referenční) — vendorovaný, ne systémový |
| `templates/model-skeleton.yaml` | Kostra instance k vyplnění |

## Viz také

Skill je výřez z většího celku a tyhle sousedy s sebou nenese:

- **návrh schématu**, když `analytical-doc` na dokument nesedí
- **plnění modelu z researche** místo z jednoho hotového dokumentu
- **kontrola rozporů** nad `*-claims.json`, který emituje `emit_claims.py`

Emitor tvrzení tu zůstal schválně: jeho výstup je vstup pro takovou kontrolu,
ať už ji pustíš čímkoli.
