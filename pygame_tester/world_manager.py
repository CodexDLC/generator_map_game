# ПЕРЕПИШИТЕ ФАЙЛ: pygame_tester/world_manager.py
import json
import pathlib
from typing import Dict, Tuple

from game_engine.core.preset import Preset
from game_engine.core.utils.rle import decode_rle_rows
from game_engine.core.constants import ID_TO_KIND
from game_engine.game_logic.transition_manager import WorldTransitionManager

# --- ИЗМЕНЕНИЕ: УДАЛЯЕМ ВСЕ ИМПОРТЫ, СВЯЗАННЫЕ С ГЕНЕРАЦИЕЙ ---
# from game_engine.world_structure.regions import RegionManager
# from game_engine.generators._base.generator import BaseGenerator

from .config import PRESET_PATH, ARTIFACTS_ROOT


class WorldManager:
    def __init__(self, city_seed: int):
        self.city_seed = city_seed
        self.preset = self._load_preset()

        # --- ИЗМЕНЕНИЕ: WorldManager больше ничего не знает о генерации ---
        # self.region_manager = ... # <-- УДАЛЕНО

        self.cache: Dict[Tuple, Dict | None] = {}
        self.world_id = "city"
        self.current_seed = city_seed
        self.transition_manager = WorldTransitionManager(self)

    def get_chunk_data(self, cx: int, cz: int) -> Dict | None:
        """
        Загружает финальные данные чанка с диска.
        """
        # --- ИЗМЕНЕНИЕ: Умное логирование ---
        if self.world_id == "city":
            # Если мы в городе, это просто загрузка статического файла
            print(f"\n[Client] Loading static asset: ({self.world_id}, pos=({cx},{cz}))...")
        else:
            # А вот если мы в мире, это запрос к процедурно сгенерированным данным
            print(f"\n[Client] Loading procedural chunk: ({self.world_id}, seed={self.current_seed}, pos=({cx},{cz}))...")
        # --- КОНЕЦ ИЗМЕНЕНИЯ ---

        key = (self.world_id, self.current_seed, cx, cz)
        if key in self.cache:
            return self.cache[key]

        chunk_path = self._get_chunk_path(self.world_id, self.current_seed, cx, cz)
        rle_path = chunk_path / "chunk.rle.json"

        if not rle_path.exists():
            print(f"[Client] -> File not found at: {rle_path}")
            # Если мы вышли за пределы сгенерированного региона, WorldActor нужно будет вызвать снова
            # TODO: Добавить вызов WorldActor для генерации новых регионов "на лету"
            return None

        try:
            with open(rle_path, "r", encoding="utf-8") as f: doc = json.load(f)
            layers = doc.get("layers")
            kind_payload = layers.get("kind", {}) if layers else doc
            height_payload = layers.get("height_q", {}) if layers else {}
            decoded_rows = decode_rle_rows(kind_payload.get("rows", []))
            kind_grid = [[ID_TO_KIND.get(int(v), "void") if not isinstance(v, str) else v for v in row] for row in decoded_rows]
            height_grid = decode_rle_rows(height_payload.get("rows", []))
            if kind_grid and not height_grid:
                height_grid = [[0.0] * len(kind_grid[0]) for _ in range(len(kind_grid))]
            decoded = {"kind": kind_grid, "height": height_grid}
            self.cache[key] = decoded
            return decoded
        except Exception as e:
            print(f"!!! [Client] CRITICAL ERROR: Failed to load or decode chunk. Error: {e}")
            return None

    def _load_preset(self) -> Preset:
        with open(PRESET_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return Preset.from_dict(data)

    def _get_chunk_path(self, world_id: str, seed: int, cx: int, cz: int) -> pathlib.Path:
        if world_id == "city":
            return ARTIFACTS_ROOT / "world" / "city" / "static" / f"{cx}_{cz}"
        else:
            # Путь к финальным, клиентским данным
            return ARTIFACTS_ROOT / "world" / world_id / str(seed) / f"{cx}_{cz}"