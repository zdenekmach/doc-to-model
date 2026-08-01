# Extrakce — jak z dokumentu naplnit instanci věrně

Extrakce je jediný nedeterministický krok celého řetězce. Všechno za ní je skript.
Proto se veškerá disciplína soustředí sem.

---

## Základní postoj

Model **nesmí tvrdit víc než zdroj**. Když dokument neříká, do kdy se má něco stihnout,
model nemá termín — a v reportu děr se objeví „požadavek bez akceptace". To není
nedostatek modelu, to je nález o dokumentu.

Pokušení je opačné: model vypadá lépe, když je vyplněný. Vyplněný model, který si domyslel
polovinu, je ale horší než původní dokument, protože působí spolehlivěji.

---

## Postup

### 1. První průchod — mapa dokumentu
Přečti celý dokument a poznamenej si, které sekce schématu vůbec připadají v úvahu.
U výkladu předpisu často nebude datový model. U procesní analýzy nebudou nefunkční
požadavky. Prázdná sekce se prostě vynechá.

### 2. Založ `sources` dřív než cokoli jiného
Rozděl zdroj na místa, na která se dá odkázat — kapitoly, paragrafy, odstavce.

```yaml
sources:
  - id: S1
    title: "Zákon č. 30/2024 Sb."
    locator: "§ 12 odst. 3"
  - id: S2
    title: "Interní metodika mzdy"
    locator: "kap. 4.2, s. 17"
```

Bez tohohle kroku se citace dodělávají zpětně a dopadne to špatně.

### 3. Rozhodni u každé věty: tvrzení, nebo požadavek?

Otázka zní: **říká ta věta, co se má stát, nebo jak to je?**

| Věta ze zdroje | Typ | Proč |
|----------------|-----|------|
| „ČNB je regulátorem pro oblast platebních služeb." | tvrzení | popisuje svět, nikoho k ničemu nezavazuje |
| „Zaměstnavatel odešle hlášení do 20. dne." | požadavek | ukládá povinnost |
| „Trh je zralý a konsolidovaný." | tvrzení | hodnocení stavu |
| „Systém musí uchovat protokoly šest měsíců." | požadavek | normativní |

Past je u vět, které vypadají popisně, ale povinnost nesou: *„Protokoly se
uchovávají šest měsíců."* V předpisu je to povinnost, v popisu stávajícího stavu
tvrzení. **Rozhoduje dokument, ne slovosled.** Když to z něj nejde poznat, zapiš
tvrzení a otázku dej do `open_questions` — model nemá vyrábět povinnost, kterou
zdroj neuložil.

U tvrzení vyplň `claim_type`:

- **fakt** — dá se dohledat a ověřit
- **výklad** — něčí čtení předpisu nebo dat
- **predikce** — o budoucnosti, ověřit nejde
- **definice** — zavádí pojem

Predikce s `confidence: explicit` je rozpor sama v sobě a report děr ji vytáhne.
Budoucnost nemůže být ve zdroji doslova.

Pole `basis` je **opora tvrzení podle zdroje** — o co se opírá (měření, odkaz na
předpis, stanovisko). Když zdroj nic takového neuvádí, nech prázdné; je to nález,
ne mezera k vyplnění.

### 4. Vytahuj tvrzení, ne odstavce
Jeden požadavek = jedna ověřitelná věc. Když věta obsahuje dvě povinnosti, jsou to dva
požadavky.

```yaml
requirements:
  - id: FR-01
    title: "Odeslat hlášení do centrální evidence"
    priority: MUST
    description: "Zaměstnavatel odesílá měsíční hlášení do centrální evidence."
    acceptance:
      - "Hlášení je odesláno do 20. dne následujícího měsíce."
    source: S1
    confidence: explicit
```

### 5. Rozliš jistotu

| `confidence` | Kdy |
|--------------|-----|
| `explicit` | Ve zdroji je to napsáno |
| `derived` | Plyne to z kombinace více míst, každé samo o sobě nestačí |
| `assumed` | Ve zdroji to není a doplnil jsi to, aby model dával smysl |

`assumed` je legitimní, ale jen když je viditelné. Report děr ho vytáhne na světlo.

### 6. Proces kresli, až když ve zdroji je
Když dokument popisuje sled kroků, zaznamenej ho. Když nepopisuje, `process` vynech —
vymyšlený diagram je nejrychlejší způsob, jak ztratit důvěru čtenáře, který doménu zná.

Krok pojmenuj slovesem („Ověř nárok", ne „Ověření nároku"). Diagram pak dává smysl bez
legendy.

### 7. Otevřené otázky
Všechno, na co ses při extrakci ptal a dokument neodpověděl, patří sem. Tahle sekce
je při předání autorovi obvykle nejužitečnější částí celého výstupu.

---

## Časté pasti

| Past | Projev | Co s tím |
|------|--------|----------|
| **Sloučení scope** | Dvě různá pravidla se stejným klíčem, ale jiným rozsahem platnosti, se slijí v jedno | Rozsah zapiš do `description` nebo rozděl na dva požadavky |
| **Ztráta podmínky** | „Do 30 dnů" bez „pokud zaměstnanec požádá" | Podmínka patří do textu požadavku, jinak vzniká falešný rozpor |
| **Nadinterpretace priorit** | Zdroj neříká MUST/SHOULD, extrakce to doplní | Priorita se vyplňuje jen když ji zdroj má, jinak vynech |
| **Diagram z ničeho** | Proces se odvodí z výčtu, který nebyl sledem | Vynech `process` |
| **Citace na celý dokument** | Všechny požadavky odkazují na jediný `source` | Rozděl zdroj na místa (krok 2) |

---

## Kontrola věrnosti

Po extrakci projdi zpětně: vezmi tři náhodné požadavky z modelu a najdi je ve zdroji.
Když je nenajdeš doslova ani jako zřejmý důsledek, extrakce si vymýšlí a je potřeba
ji přepsat, ne opravit.

Pak spusť validaci a report děr. Když report nenašel nic, je to podezřelé — reálné
dokumenty díry mají.
