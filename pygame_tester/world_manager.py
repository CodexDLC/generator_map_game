# pygame_tester/world_manager.py
import json
import pathlib
from typing import Dict, Tuple

from game_engine.core.preset import Preset
from game_engine.core.utils.rle import decode_rle_rows
from game_engine.core.constants import (
    SURFACE_ID_TO_KIND, NAV_ID_TO_KIND, KIND_GROUND, NAV_PASSABLE,
    NAV_OBSTACLE, NAV_WATER, NAV_BRIDGE
)

from .config import PRESET_PATH, ARTIFACTS_ROOT


class WorldManager:
    def __init__(self, world_seed: int):
        self.world_seed = world_seed
        self.preset = self._load_preset()
        self.cache: Dict[Tuple, Dict | None] = {}
        self.world_id = "world_location"
        self.current_seed = world_seed  # <--- Атрибут определён здесь


    def get_chunk_data(self, cx: int, cz: int) -> Dict | None:

        key = (self.world_id, self.current_seed, cx, cz)
        if key in self.cache:
            return self.cache[key]

        # ... остальная часть функции get_chunk_data, как в предыдущих ответах ...
        if self.world_id == "city":
            print(f"\n[Client] Loading static asset: ({self.world_id}, pos=({cx},{cz}))...")
        else:
            print(
                f"\n[Client] Loading procedural chunk: ({self.world_id}, seed={self.current_seed}, pos=({cx},{cz}))...")

        chunk_path = self._get_chunk_path(self.world_id, self.current_seed, cx, cz)
        rle_path = chunk_path / "chunk.rle.json"

        if not rle_path.exists():
            print(f"[Client] -> File not found at: {rle_path}")
            return None
        try:
            with open(rle_path, "r", encoding="utf-8") as f:
                doc = json.load(f)
            surface_grid, nav_grid, height_grid = [], [], []
            if "layers" in doc:
                layers = doc["layers"]
                s_rows = layers.get("surface", {}).get("rows", [])
                n_rows = layers.get("navigation", {}).get("rows", [])
                h_rows = layers.get("height_q", {}).get("rows", [])
                surface_grid = [[SURFACE_ID_TO_KIND.get(int(v), "void") for v in row] for row in
                                decode_rle_rows(s_rows)]
                nav_grid = [[NAV_ID_TO_KIND.get(int(v), "passable") for v in row] for row in decode_rle_rows(n_rows)]
                height_grid = decode_rle_rows(h_rows)
            else:
                decoded_rows = decode_rle_rows(doc.get("rows", []))
                old_id_map = {0: "ground", 1: "obstacle_prop", 2: "water", 3: "road", 7: "bridge"}
                w = doc.get("w", 128)
                h = doc.get("h", 128)
                surface_grid = [[KIND_GROUND for _ in range(w)] for _ in range(h)]
                nav_grid = [[NAV_PASSABLE for _ in range(w)] for _ in range(h)]
                for z, row in enumerate(decoded_rows):
                    for x, old_id in enumerate(row):
                        kind = old_id_map.get(old_id, "ground")
                        if kind in ["ground", "road"]:
                            surface_grid[z][x] = kind
                            nav_grid[z][x] = NAV_PASSABLE
                        elif kind == "bridge":
                            surface_grid[z][x] = "road"
                            nav_grid[z][x] = NAV_BRIDGE
                        elif kind in ["obstacle_prop", "water"]:
                            surface_grid[z][x] = KIND_GROUND
                            nav_grid[z][x] = NAV_OBSTACLE if kind == "obstacle_prop" else NAV_WATER
                height_grid = [[0.0] * w for _ in range(h)]
            decoded = {"surface": surface_grid, "navigation": nav_grid, "height": height_grid}
            self.cache[key] = decoded
            return decoded
        except Exception as e:
            print(f"!!! [Client] CRITICAL ERROR: Failed to load or decode chunk. Error: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _load_preset(self) -> Preset:
        with open(PRESET_PATH, "r", encoding="utf-8") as f: data = json.load(f)
        return Preset.from_dict(data)

    def _get_chunk_path(self, world_id: str, seed: int, cx: int, cz: int) -> pathlib.Path:
        if world_id == "city":
            return ARTIFACTS_ROOT / "world" / "city" / "static" / f"{cx}_{cz}"
        else:
            return ARTIFACTS_ROOT / "world" / world_id / str(seed) / f"{cx}_{cz}"