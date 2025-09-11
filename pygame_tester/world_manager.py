# pygame_tester/world_manager.py
import json
import pathlib
import struct
from typing import Dict, Tuple
import numpy as np

from game_engine_restructured.core.constants import SURFACE_ID_TO_KIND, NAV_PASSABLE
from game_engine_restructured.core.grid.hex import HexGridSpec
from game_engine_restructured.core.preset import Preset, load_preset
from .config import PRESET_PATH, ARTIFACTS_ROOT, CHUNK_SIZE


class WorldManager:
    def __init__(self, world_seed: int):
        self.world_seed = world_seed
        self.preset = self._load_preset()
        self.cache: Dict[Tuple, Dict | None] = {}
        self.world_id = "world_location"
        self.current_seed = world_seed
        self.grid_spec = HexGridSpec(
            edge_m=0.63, meters_per_pixel=0.25, chunk_px=CHUNK_SIZE
        )

    def get_chunk_data(self, cx: int, cz: int) -> Dict | None:
        """
        Загружает данные чанка из НОВОЙ файловой структуры.
        Читает chunk.json, heightmap.r16, objects.json и control.r32.
        """
        key = (self.world_id, self.current_seed, cx, cz)
        if key in self.cache:
            return self.cache[key]

        print(
            f"\n[Client] Loading chunk from new format: pos=({cx},{cz})..."
        )

        chunk_dir = self._get_chunk_path(self.world_id, self.current_seed, cx, cz)
        meta_path = chunk_dir / "chunk.json"

        if not meta_path.exists():
            print(f"[Client] -> Meta file not found: {meta_path}")
            self.cache[key] = None
            return None

        try:
            # --- ШАГ 1: Загружаем все доступные клиентские ассеты ---

            # Загружаем карту высот (код без изменений)
            heightmap_path = chunk_dir / "heightmap.r16"
            raw_bytes_h = heightmap_path.read_bytes()
            expected_size = CHUNK_SIZE * CHUNK_SIZE * 2
            if len(raw_bytes_h) != expected_size:
                print(f"[Client] -> ERROR: Corrupted heightmap.r16 for chunk ({cx},{cz})")
                self.cache[key] = None
                return None
            height_values = list(struct.unpack(f'<{CHUNK_SIZE * CHUNK_SIZE}H', raw_bytes_h))
            max_h = float(self.preset.elevation.get("max_height_m", 150.0))
            height_grid_m = [[(val / 65535.0) * max_h for val in
                              [height_values[i * CHUNK_SIZE:(i + 1) * CHUNK_SIZE] for i in range(CHUNK_SIZE)][row_idx]]
                             for row_idx in range(CHUNK_SIZE)]

            # Загружаем объекты (код без изменений)
            objects_path = chunk_dir / "objects.json"
            placed_objects = []
            if objects_path.exists():
                with open(objects_path, "r", encoding="utf-8") as f:
                    placed_objects = json.load(f)

            # --- ШАГ 2: Читаем и расшифровываем control.r32 для surface_grid ---
            controlmap_path = chunk_dir / "control.r32"
            raw_bytes_c = controlmap_path.read_bytes()
            control_values = struct.unpack(f'<{CHUNK_SIZE * CHUNK_SIZE}I', raw_bytes_c)

            surface_grid = [["" for _ in range(CHUNK_SIZE)] for _ in range(CHUNK_SIZE)]
            for i, val in enumerate(control_values):
                row = i // CHUNK_SIZE
                col = i % CHUNK_SIZE

                # Извлекаем 5 бит ID базовой поверхности
                base_id = (val >> 27) & 0x1F
                surface_grid[row][col] = SURFACE_ID_TO_KIND.get(base_id, "void")

            # --- ШАГ 3: Эмулируем остальные слои, которые нам пока не нужны ---
            nav_grid = [[NAV_PASSABLE for _ in range(CHUNK_SIZE)] for _ in range(CHUNK_SIZE)]
            overlay_grid = [[0 for _ in range(CHUNK_SIZE)] for _ in range(CHUNK_SIZE)]

            decoded = {
                "surface": surface_grid,
                "navigation": nav_grid,
                "overlay": overlay_grid,
                "height": height_grid_m,
                "objects": placed_objects
            }
            self.cache[key] = decoded
            return decoded

        except Exception as e:
            print(f"!!! [Client] CRITICAL ERROR: Failed to load or decode chunk. Error: {e}")
            import traceback
            traceback.print_exc()
            self.cache[key] = None
            return None

    def _load_preset(self) -> Preset:
        with open(PRESET_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return load_preset(data)

    def _get_chunk_path(self, world_id: str, seed: int, cx: int, cz: int) -> pathlib.Path:
        return ARTIFACTS_ROOT / "world" / world_id / str(seed) / f"{cx}_{cz}"

    def load_raw_json(self, cx: int, cz: int, layer_name: str) -> np.ndarray | None:
        """
        Загружает "сырые" данные слоя для одного чанка.
        Если данные региональные, "вырезает" нужный фрагмент.
        """
        region_size = self.preset.region_size
        offset = region_size // 2
        scx = (cx + offset) // region_size if cx >= -offset else (cx - offset) // region_size
        scz = (cz + offset) // region_size if cz >= -offset else (cz - offset) // region_size

        raw_dir = ARTIFACTS_ROOT / "world_raw" / str(self.world_seed) / "regions" / f"{scx}_{scz}"
        file_path = raw_dir / f"{layer_name}.json"

        if not file_path.exists():
            print(f"--- WARN: Raw layer '{layer_name}' not found at {file_path}")
            return None

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                full_grid = np.array(data.get("data"))

            # --- ИСПРАВЛЕНИЕ: Вырезаем нужный чанк из региона ---
            base_cx = scx * region_size - offset
            base_cz = scz * region_size - offset

            local_cx = cx - base_cx
            local_cz = cz - base_cz

            start_x = local_cx * CHUNK_SIZE
            start_z = local_cz * CHUNK_SIZE
            end_x = start_x + CHUNK_SIZE
            end_z = start_z + CHUNK_SIZE

            chunk_grid = full_grid[start_z:end_z, start_x:end_x]
            return chunk_grid

        except (IOError, json.JSONDecodeError) as e:
            print(f"--- ERROR: Failed to load raw JSON from {file_path}: {e}")
            return None