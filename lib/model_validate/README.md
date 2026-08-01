# model-validate — sdílený validátor strukturované pravdy

Jedna volatelná jednotka, kterou volá víc skillů (`doc-consistency`, `domain-model`,
emitory) místo 3 kopií validace. Součást substrátu strukturované pravdy (PRD
`10-Projects/system-evolution/outputs/2026-07-23-prd-structured-truth-substrate.md`,
Fáze 1).

## Vrstvy

| Vrstva | Co ověří | Kde | Determinismus |
|--------|----------|-----|---------------|
| **L1 strukturální** | enum, required, typy, kardinalita | `linkml-validate` (shell-out) | ano, blokuje |
| **L2 referenční** | unikátnost id, dangling reference | `referential.py` (schema-driven) | ano, blokuje |
| **L3 sémantická** | rozpory faktů (AI contradiction) | NENÍ tady — invokuje wrapper skill přes `contradiction-verifier` | ne, radí |

L1+L2 jsou deterministické a testovatelné — proto žijí v knihovně. L3 je LLM operace,
běží přes Claude Code (subscription), ne přes API-klíč skript → zůstává ve skillu.

## Schema-driven (žádné hardcodování domény)

`referential.py` odvozuje pravidla ze schématu přes `SchemaView`:

- **identifikátorové třídy** = mají slot `identifier: true` → jejich instance nesou id
- **referenční sloty** = `range` je třída s identifikátorem A slot **není** inlined
  (inlined = embedded objekt/containment, ne odkaz)
- **id-rodina** = nejvyšší předek sdílející identifikátor (Actor→Entity), aby
  reference s `range: Entity` resolvovala i na `Actor`/`Concept`/`Artifact`

Ověřeno na ESG pilotu i na nesouvisejícím schématu (Library/Book/Loan) — nula vazby
na konkrétní názvy tříd/slotů.

## Použití (CLI)

```bash
python3 .claude/scripts/model-validate/validate.py \
  --schema domena.linkml.yaml \
  --data instance.yaml \
  [--class Root]          # cílová třída kořene; default = tree_root ze schématu
  [--skip-structural]     # jen L2 (když linkml-validate není/nechceš)
  [--json]                # strojový výstup
```

Exit: `0` OK · `1` validační chyby · `2` chyba použití/běhu.

## Použití (jako knihovna)

```python
import sys; sys.path.insert(0, ".claude/scripts/model-validate")
from validate import validate
r = validate("domena.linkml.yaml", "instance.yaml")   # dict: {ok, structural, referential}
# nebo jen L2:
from referential import ReferentialChecker
errs = ReferentialChecker("domena.linkml.yaml").check(yaml.safe_load(open("instance.yaml")))
```

## Závislosti

LinkML (`pip install linkml`). L2 potřebuje jen `linkml_runtime` + `pyyaml`; L1 volá
CLI `linkml-validate`. Runtime lock-in žádný — Pydantic/generátory jsou čistý Python.

## Test

```bash
P=10-Projects/system-evolution/outputs/linkml-pilot-esg
python3 .claude/scripts/model-validate/validate.py -s $P/esg_domain.linkml.yaml -d $P/esg_data.yaml         # ✓ exit 0
python3 .claude/scripts/model-validate/validate.py -s $P/esg_domain.linkml.yaml -d $P/esg_data_broken.yaml  # ✗ exit 1 (dup id + dangling + enum + required)
```
