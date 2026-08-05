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

Tohle pravidlo ale hlídá jen jeden směr. Model, který **tvrdí míň než zdroj**, ho
neporušuje ani trochu. Extrakce, která přečetla první kapitolu ze tří, je dokonale
věrná — to málo, co vytáhla, je doložené, takže projde validací i kontrolou opory se
samými jedničkami. Zapomenutá lhůta přitom stojí stejně jako lhůta vymyšlená.

Věrnost je proto **podmínka nutná, ne postačující**. Druhá polovina postoje zní:
z každého místa zdroje, které něco ukládá nebo tvrdí, musí v modelu něco být — nebo
musí být zapsáno, proč tam nic není.

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

#### Rozlož tvrzení na čtveřici

U tvrzení vyplň `subject`, `predicate`, `value` a `scope`. Je to **celek, ne
výběr** — vynechaný `predicate` nebo `value` znamená, že tvrzení do kontroly
rozporů vůbec nedojde. Není co s čím porovnat.

| Věta ze zdroje | subject | predicate | value | scope |
|----------------|---------|-----------|-------|-------|
| „Anotace nese 612 lokusů miRNA." | anotace miRNA | počet lokusů | 612 | Ensembl Protists 59 |
| „Hlášení se odesílá do 20. dne." | měsíční hlášení | lhůta odeslání | 20. den následujícího měsíce | JMHZ |

Ta past je zákeřná v tom, že vyplněný `subject` vypadá jako hotová práce. Reálný
případ: model se čtrnácti tvrzeními, všechna měla `subject` i `scope`, žádné
`predicate` ani `value` — do kontroly rozporů se jich dostalo nula.

`scope` chrání před falešným poplachem: 30 dnů u jednoho rozsahu a 90 u jiného
není rozpor. Proto je povinný i tam, kde se zdá zřejmý.

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

## Dvě zpětné kontroly, každá v jiném směru

Ruční verze se dá udělat na třech vzorcích a trvá minutu.

**Model → zdroj.** Vezmi tři náhodné požadavky z modelu a najdi je ve zdroji. Když
je nenajdeš doslova ani jako zřejmý důsledek, extrakce si vymýšlí a je potřeba ji
přepsat, ne opravit.

**Zdroj → model.** Otevři zdroj na třech náhodných místech, která něco ukládají nebo
tvrdí, a najdi je v modelu. Když je nenajdeš, extrakce je mělká — a to je ta chyba,
kterou první kontrola nikdy neukáže.

Skriptovanou podobu obou má pipeline: `ground_check.py` v prvním směru,
`coverage_check.py` ve druhém. Osiřelá čísla z kontroly pokrytí stojí za pohled
vždycky, protože lhůta a částka jsou to nejdražší, co se dá při extrakci ztratit.

Pak spusť validaci a report děr. Když report nenašel nic, je to podezřelé — reálné
dokumenty díry mají.

Nepokryté místo se buď doextrahuje, nebo se vědomě odepíše přes `coverage_waivers`
s důvodem. Sto procent pokrytí není cíl: kdyby se honilo číslo, extrakce si začne
vymýšlet požadavky, aby ho nasytila — a je zpátky na začátku téhle stránky.
