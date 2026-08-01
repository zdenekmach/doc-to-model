# AGENTS.md

Postup, kterým se v tomhle repozitáři dělá z dokumentu model, je popsaný ve skillu
`.github/skills/doc-to-model/SKILL.md`. Přečti si ho dřív, než začneš.

Zkrácený řetěz:

```
ingest → segment → EXTRACT (ty) → validate → ground-check → project → review
```

Tvůj jediný krok je **extrakce**. Zbytek jsou skripty a mají brány — emitor nad
neověřeným modelem odmítne běžet, takže pořadí nejde obejít.

Tvrdá pravidla: nic, co ve zdroji není, nesmí být fakt; chybějící akceptační kritérium
je nález, ne mezera k vyplnění; každý výrok nese odkaz do zdroje. Plné znění a příklady
v `references/extraction.md`.

Prostředí: `source .venv/bin/activate`, spouštět z kořene repozitáře.
