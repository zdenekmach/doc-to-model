# Kontext repozitáře doc-to-model

Tenhle repozitář dělá z analytického dokumentu strukturovanou pravdu a z ní generuje
dokument, diagram, kontext pro AI a report děr. Postup je popsaný ve skillu
`.github/skills/doc-to-model/SKILL.md` — **drž se ho, nevymýšlej vlastní pořadí kroků.**

## Pravidla, která platí vždycky

1. **Nic, co ve zdroji není, se nesmí objevit jako fakt.** Doplněné prvky dostanou
   `confidence: assumed` a patří do reportu děr. Vyplněný model vypadá lépe — a právě
   proto je domýšlení mezer tichá fabrikace.
2. **Chybějící akceptační kritérium je nález, ne mezera k vyplnění.** Nedoplňuj ho.
3. **Každý výrok dostane `source`** — odkaz do sekce `sources`. Bez toho model nejde
   ověřit proti zdroji a je horší než původní dokument, protože vypadá spolehlivěji.
4. **Neupravuj vygenerované soubory v `out/`.** Oprav model a přegeneruj.
5. **Emitory nespouštěj před validací.** Skripty to hlídají samy přes `<model>.state.json`,
   takže obcházení stejně skončí chybou.

## Prostředí

Python 3.12 ve `.venv`, závislosti v `requirements.txt`. Skripty se spouštějí
z kořene repozitáře.

```bash
source .venv/bin/activate
bash scripts/build.sh model/<nazev>/<nazev>.yaml model/<nazev>/out inputs/<zdroj>.txt
```

## Jazyk

Dokumentace, modely i commit messages česky. Kód a názvy polí ve schématu anglicky.
