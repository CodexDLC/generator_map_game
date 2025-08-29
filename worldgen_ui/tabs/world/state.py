
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, Tuple

@dataclass
class WorldState:
    seed: int = 123
    cx: int = 0
    cz: int = 0
    preset_path: str = "engine/presets/world/base_default.json"

    cache: Dict[Tuple[int,int], dict] = field(default_factory=dict)  # (cx,cz) -> chunk rle json

    def key(self) -> Tuple[int,int]:
        return (self.cx, self.cz)
