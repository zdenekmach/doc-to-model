---
name: doc-to-model
description: "Triggers: /doc-to-model, 'udělej ze specifikace strukturovanou pravdu', 'převeď dokument na SSOT', 'z dokumentu vytáhni model', 'document to single source of truth', 'analytický dokument na data', 'z toho dokumentu vygeneruj diagram a word'. Vezme EXISTUJÍCÍ analytický dokument (specifikace, procesní analýza, výklad předpisu, zadání změny) a udělá z něj jednu validovanou instanci strukturované pravdy, ze které deterministicky emituje Word, draw.io diagram, kontext pro AI a report děr. NENÍ to research o doméně (→ /domain-model) ani návrh schématu (→ /data-metamodel) ani těžba dokumentu do učebních rámců (→ /extract)."
---

# Doc → Model — z hotového dokumentu strukturovaná pravda

**Verze:** 1.6.0 | **Pattern:** INGEST → SEGMENT → EXTRACT → VALIDATE → GROUND-CHECK → PROJECT (substrát strukturované pravdy)

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

Rozhodovací hrana (kdy pattern nepoužít) je v `README.md`.
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
3. EXTRACT      → instance proti schématu, s citacemi     Claude Code
4. VALIDATE     → struktura + reference                   skript · BRÁNA
5. GROUND-CHECK → má požadavek oporu v citovaném místě    skript · BRÁNA
6. PROJECT      → Word, draw.io, kontext, díry, prohlížeč skript
7. REVIEW       → projít díry s autorem dokumentu         člověk · BRÁNA
```

Jediný krok, který zůstává na jazykovém modelu, je **EXTRACT**. Všechno před ním
i za ním je skript, a extrakce má postpodmínku (krok 5), takže se dá zkontrolovat.

Kroky 4–6 najednou: `bash scripts/build.sh <model.yaml> [out_dir] [zdroj.txt]`.
Je to zkratka, ne orchestrátor — pořadí platí i bez ní.

### 0. Vstup

Zeptej se na dvě věci, pokud nejsou zřejmé: **který dokument** a **co z něj má vzniknout**
(dokument, diagram, kontrola konzistence, kontext pro agenta — může být víc).

Cílový adresář: `model/<nazev>/`. Všechny cesty v tomhle dokumentu jsou vůči kořeni repozitáře — spouštěj odtamtud.

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
blok `sources:` k vložení do modelu. Je to **návrh, ne verdikt** — zkrať ho na
místa, na která budeš opravdu odkazovat.

Skript si své návrhy sám zkusí dohledat toutéž funkcí, kterou pak používá
prohlížeč i kontrola opory, a nahlásí poměr. Locator, který se nedá zakotvit,
by byl jen ozdoba u citace.

### 3. EXTRACT — naplnění instance

**Tohle dělá Claude Code, ne skript.** Extrakce je LLM operace a běží přes subscription,
ne přes API-klíč.

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
python3 lib/model_validate/validate.py \
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
| slabá opora · nezakotveno · bez zdroje | projít okem |
| **bez opory · visící odkaz** | **blokuje** — oprav extrakci |

Planý poplach se odbaví `--warn-only`, ale ne mlčky: report `<model>-opora.md`
zůstává a je v něm vidět, co se přeskočilo.

<gate severity="BLOCKER">
Nespouštěj emitory, dokud ground-check neprošel — pokud existuje zdrojový text.
Bez něj emitory poběží, ale nahlas upozorní, že výstup nemá ověřenou oporu.
</gate>

### 6. PROJECT

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

### 7. REVIEW

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
| Vlastní pole | `claim_type`, `basis`, `subject`, `scope` | `priority`, `acceptance`, `actor` |
| Společné | `id`, `title`, `description`, `source`, `confidence` (třída `Statement`) | totéž |

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
# claims.json je vstup pro kontrolu rozporů (deterministická vrstva)
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
| Ručně dopsat do Wordu, co v modelu chybí | Doplnit model a přegenerovat |
| Použít na jednorázový dokument | Napsat ho rovnou |

---

## Reference

| Soubor | Obsah |
|--------|-------|
| `schema/analytical-doc.linkml.yaml` | Schéma instance |
| `scripts/ingest.py` | Dokument (PDF/Word/text) → text se záchytnými body |
| `scripts/segment.py` | Návrh zdrojových míst + self-check zakotvitelnosti |
| `scripts/ground_check.py` | Postpodmínka extrakce — opora tvrzení ve zdroji |
| `scripts/pipeline_state.py` · `mark_step.py` | Brány mezi kroky (`<model>.state.json`) |
| `scripts/sourcemap.py` | Locator → řádky; sdílí prohlížeč i kontrola opory |
| `scripts/build.sh` | Zkratka pro kroky 2–4 |
| `scripts/emit_word.py` · `emit_drawio.py` · `emit_context.py` · `emit_viewer.py` · `emit_claims.py` | Emitory |
| `references/extraction.md` | Jak extrahovat věrně (pravidla, příklady, pasti) |
| `templates/model-skeleton.yaml` | Kostra instance k vyplnění |

## Viz také

- `README.md` — instalace, spuštění, rozhodovací hrana patternu
- `/doc-consistency` (PersonalSkills) — kontrola sémantických rozporů, navazuje na `emit_claims.py`
