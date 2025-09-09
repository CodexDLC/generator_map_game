from __future__ import annotations
import json
from pathlib import Path
from dataclasses import dataclass
from typing import Dict


@dataclass
class Footprint:
    type: str
    width: float = 0.0
    depth: float = 0.0


@dataclass
class Prefab:
    id: str
    name: str
    footprint: Footprint


class PrefabManager:
    def __init__(self, prefabs_path: Path):
        self.prefabs: Dict[str, Prefab] = self._load_prefabs(prefabs_path)
        print(f"[PrefabManager] Loaded {len(self.prefabs)} prefabs from catalog.")

    def _load_prefabs(self, path: Path) -> Dict[str, Prefab]:
        if not path.exists():
            print(f"!!! WARNING: Prefab catalog not found at {path}")
            return {}

        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        loaded_prefabs = {}
        for prefab_id, prefab_data in data.items():
            footprint_data = prefab_data.get("footprint", {})
            footprint = Footprint(
                type=footprint_data.get("type", "ellipse"),
                width=float(footprint_data.get("width_m", 1.0)),
                depth=float(footprint_data.get("depth_m", 1.0)),
            )
            loaded_prefabs[prefab_id] = Prefab(
                id=prefab_id,
                name=prefab_data.get("name", prefab_id),
                footprint=footprint,
            )
        return loaded_prefabs

    def get_prefab(self, prefab_id: str) -> Prefab | None:
        return self.prefabs.get(prefab_id)