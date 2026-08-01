#!/usr/bin/env python3
"""Vrstva L2 — referenční integrita nad LinkML instancí, SCHEMA-DRIVEN.

LinkML strukturální validace (L1, JSON Schema) ověří enum/required/typy/kardinalitu,
ale NE unikátnost identifikátorů ani dangling reference. Tenhle modul je „první emitor"
pro tyhle referenční invarianty — odvozuje pravidla ze schématu přes SchemaView, takže
funguje na LIBOVOLNÉ doméně (žádné hardcodované názvy tříd/slotů jako v ESG pilotu).

Odvození ze schématu:
- identifikátorové třídy = mají slot `identifier: true` (→ jejich instance nesou id)
- referenční sloty    = range je třída s identifikátorem A slot NENÍ inlined
                        (inlined = embedded objekt/containment → přeskoč, není to odkaz)
- id-rodina           = nejvyšší předek sdílející identifikátorový slot (Actor→Entity),
                        aby reference s range=Entity resolvovala i na Actor/Concept/Artifact
"""
from __future__ import annotations

import warnings
from typing import Any

warnings.filterwarnings("ignore", message=".*urllib3.*")  # linkml_runtime → requests šum
from linkml_runtime import SchemaView  # noqa: E402


class ReferentialChecker:
    def __init__(self, schema_path: str):
        self.sv = SchemaView(schema_path)
        self._classes = self.sv.all_classes()
        # id_classes: název třídy -> název jejího identifikátorového slotu
        self._id_classes: dict[str, str] = {}
        for cn in self._classes:
            idslot = self.sv.get_identifier_slot(cn, use_key=True)
            if idslot is not None:
                self._id_classes[cn] = idslot.name

    def _id_root(self, cls: str) -> str:
        """Nejvyšší identifikátorový předek — společný jmenný prostor id.

        Actor/Concept/Artifact dědí `id` z Entity → všechny sdílejí rodinu 'Entity',
        takže reference s range=Entity resolvuje na kteroukoli konkrétní podtřídu.
        """
        ancestors = self.sv.class_ancestors(cls)  # self → kořen
        id_ancestors = [a for a in ancestors if a in self._id_classes]
        return id_ancestors[-1] if id_ancestors else cls

    def _root_class(self, root_class: str | None) -> str:
        if root_class:
            return root_class
        roots = [c.name for c in self._classes.values() if c.tree_root]
        if not roots:
            raise ValueError(
                "Schéma nemá tree_root — zadej cílovou třídu kořenového objektu "
                "explicitně (--class)."
            )
        return roots[0]

    def check(self, data: dict[str, Any], root_class: str | None = None) -> list[str]:
        """Vrať seznam referenčních chyb (prázdný = OK)."""
        root = self._root_class(root_class)
        # ids_by_root[rodina] -> {id: počet výskytů}  (dup detekce)
        ids_by_root: dict[str, dict[str, int]] = {}
        # refs: (owner_id, slot, target_id, target_root)
        refs: list[tuple[str, str, str, str]] = []
        errors: list[str] = []

        def register_id(cls: str, obj: dict) -> str | None:
            idname = self._id_classes.get(cls)
            if not idname:
                return None
            idval = obj.get(idname)
            if idval is None:
                return None
            fam = ids_by_root.setdefault(self._id_root(cls), {})
            fam[idval] = fam.get(idval, 0) + 1
            return idval

        def walk(obj: Any, cls: str) -> None:
            if not isinstance(obj, dict):
                return
            owner_id = register_id(cls, obj)
            for slot in self.sv.class_induced_slots(cls):
                if slot.range not in self._classes:
                    continue  # skalár / enum → neřešíme
                val = obj.get(slot.name)
                if val is None:
                    continue
                items = val if isinstance(val, list) else [val]
                inlined = bool(slot.inlined or slot.inlined_as_list)
                if inlined:
                    for it in items:
                        walk(it, slot.range)
                else:
                    # non-inlined class-range = ODKAZ na id existující entity
                    target_root = self._id_root(slot.range)
                    for it in items:
                        tid = it.get(self._id_classes.get(slot.range, "id")) if isinstance(it, dict) else it
                        refs.append((owner_id or "?", slot.name, tid, target_root))

        walk(data, root)

        # 1) unikátnost identifikátorů v rámci rodiny
        for fam, counts in ids_by_root.items():
            for idval, n in counts.items():
                if n > 1:
                    errors.append(f"duplicitní id {idval!r} v rodině {fam} ({n}×)")

        # 2) dangling reference
        for owner_id, slot, tid, target_root in refs:
            known = ids_by_root.get(target_root, {})
            if tid not in known:
                errors.append(
                    f"{owner_id}: {slot}={tid!r} → entita neexistuje (dangling reference)"
                )

        return errors
