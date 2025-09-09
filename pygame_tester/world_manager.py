# pygame_tester/world_manager.py
import json
import pathlib
from typing import Dict, Tuple

from game_engine.core.preset import load_preset, Preset
from game_engine.core.utils.rle import decode_rle_rows
from game_engine.core.constants import (
    SURFACE_ID_TO_KIND,
    NAV_ID_TO_KIND
)
from game_engine.core.grid.hex import HexGridSpec

from .config import PRESET_PATH, ARTIFACTS_ROOT, CHUNK_SIZE


class WorldManager:
    def __init__(self, world_seed: int):
        self.world_seed = world_seed
        self.preset = self._load_preset()
        self.cache: Dict[Tuple, Dict | None] = {}
        self.world_id = "world_location"
        self.current_seed = world_seed
        self.grid_spec = HexGridSpec(
            edge_m=0.63, meters_per_pixel=0.8, chunk_px=CHUNK_SIZE
        )

    def get_chunk_data(self, cx: int, cz: int) -> Dict | None:
        """
        Загружает данные чанка из новой файловой структуры (meta.json + слои).
        """
        key = (self.world_id, self.current_seed, cx, cz)
        if key in self.cache:
            return self.cache[key]

        print(
            f"\n[Client] Loading chunk: ({self.world_id}, seed={self.current_seed}, pos=({cx},{cz}))..."
        )

        chunk_dir = self._get_chunk_path(self.world_id, self.current_seed, cx, cz)
        meta_path = chunk_dir / "chunk.json"

        if not meta_path.exists():
            print(f"[Client] -> Meta file not found: {meta_path}")
            self.cache[key] = None
            return None

        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                meta_doc = json.load(f)

            decoded_layers = {}
            layer_files = meta_doc.get("layer_files", {})

            # Загрузка слоя surface
            if "surface" in layer_files:
                path = chunk_dir / layer_files["surface"]
                with open(path, "r", encoding="utf-8") as f:
                    s_rows = json.load(f).get("rows", [])
                decoded_layers["surface"] = [
                    [SURFACE_ID_TO_KIND.get(int(v), "ground") for v in row]
                    for row in decode_rle_rows(s_rows)
                ]

            # Загрузка слоя navigation
            if "navigation" in layer_files:
                path = chunk_dir / layer_files["navigation"]
                with open(path, "r", encoding="utf-8") as f:
                    n_rows = json.load(f).get("rows", [])
                decoded_layers["navigation"] = [
                    [NAV_ID_TO_KIND.get(int(v), "passable") for v in row]
                    for row in decode_rle_rows(n_rows)
                ]

            # Загрузка слоя height
            if "height_q" in layer_files:
                path = chunk_dir / layer_files["height_q"]
                with open(path, "r", encoding="utf-8") as f:
                    h_rows = json.load(f).get("rows", [])
                decoded_layers["height"] = decode_rle_rows(h_rows)

            # Загрузка слоя overlay
            if "overlay" in layer_files:
                path = chunk_dir / layer_files["overlay"]
                with open(path, "r", encoding="utf-8") as f:
                    o_rows = json.load(f).get("rows", [])
                decoded_layers["overlay"] = decode_rle_rows(o_rows)

            self.cache[key] = decoded_layers
            return decoded_layers

        except Exception as e:
            print(
                f"!!! [Client] CRITICAL ERROR: Failed to load or decode chunk. Error: {e}"
            )
            import traceback
            traceback.print_exc()
            self.cache[key] = None
            return None

    def _load_preset(self) -> Preset:
        with open(PRESET_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return load_preset(data)

    def _get_chunk_path(self, world_id: str, seed: int, cx: int, cz: int) -> pathlib.Path:
        if world_id == "city":
            return ARTIFACTS_ROOT / "world" / "city" / "static" / f"{cx}_{cz}"
        else:
            return ARTIFACTS_ROOT / "world" / world_id / str(seed) / f"{cx}_{cz}"