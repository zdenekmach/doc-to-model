#!/usr/bin/env python3
"""pipeline_state.py — kdo co odbavil nad kterou verzí modelu.

Pořadí kroků drží skill (SKILL.md). Aby ho nešlo obejít nedopatřením, každý krok
si sem zapíše, že proběhl, a to spolu s otiskem modelu. Následující krok si
předpoklad ověří a nad neověřeným nebo mezitím změněným modelem odmítne běžet.

Stav žije vedle modelu jako `<model>.state.json`. Je to odvozený soubor —
smazáním se nic neztratí, jen se kroky musí zopakovat.
"""
import hashlib
import json
import sys
from pathlib import Path


def state_path(model: Path) -> Path:
    return model.with_suffix(model.suffix + ".state.json")


def model_hash(model: Path) -> str:
    return hashlib.sha256(model.read_bytes()).hexdigest()[:16]


def load(model: Path) -> dict:
    p = state_path(model)
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def record(model: Path, step: str, ok: bool = True, detail=None):
    """Zapíše výsledek kroku pro aktuální otisk modelu."""
    st = load(model)
    h = model_hash(model)
    if st.get("model_hash") != h:
        st = {"model_hash": h, "steps": {}}
    st.setdefault("steps", {})[step] = {"ok": bool(ok), "detail": detail}
    state_path(model).write_text(
        json.dumps(st, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def passed(model: Path, step: str) -> bool:
    st = load(model)
    if st.get("model_hash") != model_hash(model):
        return False
    return bool(st.get("steps", {}).get(step, {}).get("ok"))


def warn_if_missing(model: Path, step: str, why: str):
    """Měkké upozornění — krok chybí, ale zastavovat kvůli tomu by bylo přísné.

    Tiché přeskočení by ale bylo horší: artefakt vypadá stejně důvěryhodně,
    ať kontrola proběhla nebo ne.
    """
    if not passed(model, step):
        print(f"[POZOR] {step} neproběhl nad touto verzí modelu — {why}",
              file=sys.stderr)


def require(model: Path, steps, current: str):
    """Tvrdá brána: bez uvedených kroků se `current` nespustí.

    Chybová hláška říká, co spustit — jinak by se pravidlo obcházelo tím,
    že nikdo neví jak ho splnit.
    """
    missing = [s for s in steps if not passed(model, s)]
    if not missing:
        return
    hint = {
        "validate": "python3 .../model-validate/validate.py --schema … --data <model> --class Document",
        "ground-check": "python3 ground-check.py --model <model> --source <zdroj.txt>",
    }
    lines = [
        f"[BRÁNA] Krok {current} nelze spustit — chybí: {', '.join(missing)}.",
        "Model se od posledního ověření změnil, nebo krok ještě neproběhl.",
    ]
    lines += [f"  → {hint[s]}" for s in missing if s in hint]
    sys.exit("\n".join(lines))
