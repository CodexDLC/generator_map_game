# pygame_tester/world_manager.py
import json
import pathlib
import struct
from typing import Dict, Tuple

from game_engine.core.preset import load_preset, Preset
from game_engine.core.constants import (
    KIND_GROUND,
    NAV_PASSABLE
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
            edge_m=0.63, meters_per_pixel=0.25, chunk_px=CHUNK_SIZE
        )

    def get_chunk_data(self, cx: int, cz: int) -> Dict | None:
        """
        Загружает данные чанка из НОВОЙ файловой структуры.
        Читает chunk.json, heightmap.r16 и objects.json.
        Логические слои (surface, navigation) эмулирует "на лету" для тестера.
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

            # Загружаем карту высот
            heightmap_path = chunk_dir / "heightmap.r16"
            raw_bytes = heightmap_path.read_bytes()
            # Убеждаемся, что размер файла корректен
            expected_size = CHUNK_SIZE * CHUNK_SIZE * 2
            if len(raw_bytes) != expected_size:
                print(f"[Client] -> ERROR: Corrupted heightmap.r16 for chunk ({cx},{cz})")
                self.cache[key] = None
                return None

            height_values = list(struct.unpack(f'<{CHUNK_SIZE * CHUNK_SIZE}H', raw_bytes))
            # Нормализуем обратно в метры
            max_h = float(self.preset.elevation.get("max_height_m", 150.0))
            height_grid_m = [[(val / 65535.0) * max_h for val in
                              [height_values[i * CHUNK_SIZE:(i + 1) * CHUNK_SIZE] for i in range(CHUNK_SIZE)][row_idx]]
                             for row_idx in range(CHUNK_SIZE)]

            # Загружаем объекты
            objects_path = chunk_dir / "objects.json"
            placed_objects = []
            if objects_path.exists():
                with open(objects_path, "r", encoding="utf-8") as f:
                    placed_objects = json.load(f)

            # --- ШАГ 2: "Эмулируем" логические слои для тестера ---
            # Так как кисти пока отключены, мы создадим простые слои для отображения.
            # В будущем эта логика будет браться из `navigation.rle.json` и `surface.rle.json`,
            # которые тестер будет загружать как "сервер".

            surface_grid = [[KIND_GROUND for _ in range(CHUNK_SIZE)] for _ in range(CHUNK_SIZE)]
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