# pygame_tester/world_manager.py
import json
import pathlib
from typing import Dict, Tuple

from game_engine.core.preset import load_preset, Preset
from game_engine.core.utils.rle import decode_rle_rows
from game_engine.core.constants import (
    SURFACE_ID_TO_KIND,
    NAV_ID_TO_KIND,
    KIND_GROUND,
    NAV_PASSABLE,
    NAV_OBSTACLE,
    NAV_WATER,
    NAV_BRIDGE,
)
from game_engine.core.grid.hex import HexGridSpec  # <-- НОВЫЙ ИМПОРТ

from .config import PRESET_PATH, ARTIFACTS_ROOT, CHUNK_SIZE


class WorldManager:
    def __init__(self, world_seed: int):
        self.world_seed = world_seed
        self.preset = self._load_preset()
        self.cache: Dict[Tuple, Dict | None] = {}
        self.world_id = "world_location"
        self.current_seed = world_seed
        # --- НАЧАЛО ИЗМЕНЕНИЙ: Создаем spec для гексов ---
        self.grid_spec = HexGridSpec(
            edge_m=0.63, meters_per_pixel=0.8, chunk_px=CHUNK_SIZE
        )
        # --- КОНЕЦ ИЗМЕНЕНИЙ ---

    # --- ИЗМЕНЕНИЯ: Теперь принимаем гексагональные координаты ---
    def get_chunk_data(self, q: int, r: int) -> Dict | None:
        cx = q // self.preset.size
        cz = r // self.preset.size

        key = (self.world_id, self.current_seed, cx, cz)
        if key in self.cache:
            return self.cache[key]

        print(
            f"\n[Client] Loading procedural chunk: ({self.world_id}, seed={self.current_seed}, pos=({cx},{cz}))..."
        )

        chunk_path = self._get_chunk_path(self.world_id, self.current_seed, cx, cz)
        rle_path = chunk_path / "chunk.rle.json"

        if not rle_path.exists():
            print(f"[Client] -> RLE not found, try fallback: heightmap.r16")
            # --- Fallback: читаем heightmap.r16 и строим временные слои ---
            try:
                import os, struct
                hm_path = chunk_path / "heightmap.r16"
                if not hm_path.exists():
                    print(f"[Client] -> Fallback failed: {hm_path} missing")
                    return None

                # Читаем 256x256 (CHUNK_SIZE) 16-бит беззнаковые, little-endian
                raw = hm_path.read_bytes()
                expected = CHUNK_SIZE * CHUNK_SIZE * 2
                if len(raw) != expected:
                    print(f"[Client] -> Fallback failed: size mismatch {len(raw)} != {expected}")
                    return None

                # Превращаем в список списков высот (float)
                height_vals = list(struct.unpack("<" + "H" * (CHUNK_SIZE * CHUNK_SIZE), raw))
                height_grid = [height_vals[i * CHUNK_SIZE:(i + 1) * CHUNK_SIZE] for i in range(CHUNK_SIZE)]

                # Временные слои: всё passable ground, overlay=0
                surface_grid = [["ground"] * CHUNK_SIZE for _ in range(CHUNK_SIZE)]
                nav_grid = [["passable"] * CHUNK_SIZE for _ in range(CHUNK_SIZE)]
                overlay_grid = [[0] * CHUNK_SIZE for _ in range(CHUNK_SIZE)]

                decoded = {
                    "surface": surface_grid,
                    "navigation": nav_grid,
                    "overlay": overlay_grid,
                    "height": height_grid,
                }
                self.cache[key] = decoded
                return decoded
            except Exception as e:
                print(f"[Client] -> Fallback failed with error: {e}")
                return None
        try:
            with open(rle_path, "r", encoding="utf-8") as f:
                doc = json.load(f)

            if "layers" in doc:
                layers = doc["layers"]
                s_rows = layers.get("surface", {}).get("rows", [])
                n_rows = layers.get("navigation", {}).get("rows", [])
                h_rows = layers.get("height_q", {}).get("rows", [])
                o_rows = layers.get("overlay", {}).get("rows", [])

                surface_grid = [
                    [SURFACE_ID_TO_KIND.get(int(v), "ground") for v in row]
                    for row in decode_rle_rows(s_rows)
                ]
                nav_grid = [
                    [NAV_ID_TO_KIND.get(int(v), "passable") for v in row]
                    for row in decode_rle_rows(n_rows)
                ]
                overlay_grid = decode_rle_rows(o_rows)
                height_grid = decode_rle_rows(h_rows)

                decoded = {
                    "surface": surface_grid,
                    "navigation": nav_grid,
                    "overlay": overlay_grid,
                    "height": height_grid,
                }
                self.cache[key] = decoded
                return decoded
            else:
                decoded_rows = decode_rle_rows(doc.get("rows", []))
                old_id_map = {
                    0: "ground",
                    1: "obstacle_prop",
                    2: "water",
                    3: "road",
                    7: "bridge",
                }
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
                            nav_grid[z][x] = (
                                NAV_OBSTACLE if kind == "obstacle_prop" else NAV_WATER
                            )
                height_grid = [[0.0] * w for _ in range(h)]
            decoded = {
                "surface": surface_grid,
                "navigation": nav_grid,
                "height": height_grid,
            }
            self.cache[key] = decoded
            return decoded
        except Exception as e:
            print(
                f"!!! [Client] CRITICAL ERROR: Failed to load or decode chunk. Error: {e}"
            )
            import traceback

            traceback.print_exc()
            return None

    def _load_preset(self) -> Preset:
        with open(PRESET_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return load_preset(data)

    # Эта функция остается без изменений, т.к. пути к файлам все еще зависят от cx/cz
    def _get_chunk_path(self, world_id: str, seed: int, cx: int, cz: int) -> pathlib.Path:
        if world_id == "city":
            return ARTIFACTS_ROOT / "world" / "city" / "static" / f"{cx}_{cz}"
        else:
            return ARTIFACTS_ROOT / "world" / world_id / str(seed) / f"{cx}_{cz}"