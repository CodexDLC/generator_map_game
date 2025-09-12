# Файл: game_engine_restructured/world/processing/detail_processor.py
from __future__ import annotations
import json
from pathlib import Path
from typing import Any

from ...core.types import GenResult
from ...core.preset import Preset
from ..context import Region
from ..features.blending import BlendingBrush
from ..features.forests import ForestBrush
from ..features.rocks import RockBrush
from ..features.local_roads import build_local_roads
from ..prefab_manager import PrefabManager
from ..object_types import PlacedObject
from ..grid_utils import generate_hex_map_from_pixels


class DetailProcessor:
    # --- НАЧАЛО ИЗМЕНЕНИЙ ---
    def __init__(self, preset: Preset, prefab_manager: PrefabManager, verbose: bool = False):
        self.preset = preset
        self.prefab_manager = prefab_manager
        self.verbose = verbose

    # --- КОНЕЦ ИЗМЕНЕНИЙ ---

    def process(self, chunk: GenResult, region_context: Region) -> GenResult:
        if not hasattr(chunk, 'placed_objects'):
            chunk.placed_objects = []

        # --- ЭТАП 1: Применяем кисти для деталей ландшафта ---

        # 1.1. Сглаживаем переходы между текстурами
        blending_brush = BlendingBrush(chunk, self.preset)
        blending_brush.apply()

        # 1.2. Рисуем леса (пока отключено для скорости)
        # forest_brush = ForestBrush(chunk, self.preset)
        # forest_brush.apply(tree_rock_ratio=0.95, min_distance=2)

        # 1.3. Добавляем россыпи камней (пока отключено для скорости)
        # rock_brush = RockBrush(chunk, self.preset)
        # rock_brush.apply(density=0.01, near_slope_multiplier=5.0)

        # --- ЭТАП 2: Строим локальные дороги по плану ---
        build_local_roads(chunk, region_context, self.preset)

        # --- ЭТАП 3: Генерация данных для гексагональной карты сервера (пока отключено) ---
        # if chunk.grid_spec:
        #     if self.verbose:
        #         print(f"  -> Generating server hex map for chunk ({chunk.cx},{chunk.cz})...")
        #     chunk.hex_map_data = generate_hex_map_from_pixels(
        #         chunk.grid_spec,
        #         chunk.layers["surface"],
        #         chunk.layers["navigation"],
        #         chunk.layers["height_q"]["grid"]
        #     )

        chunk.capabilities["has_biomes"] = True
        chunk.capabilities["has_roads"] = True

        return chunk