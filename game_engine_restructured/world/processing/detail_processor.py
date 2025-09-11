# Файл: game_engine_restructured/world/processing/detail_processor.py
from __future__ import annotations
import json
from pathlib import Path
from typing import Any

from ...core.types import GenResult
from ...core.preset import Preset
from ..context import Region
# from ..features.biome_rules import apply_biome_rules # ВРЕМЕННО ОТКЛЮЧЕНО
# from ..features.local_roads import build_local_roads # ВРЕМЕННО ОТКЛЮЧЕНО
from ..prefab_manager import PrefabManager
from ..object_types import PlacedObject
from ..grid_utils import generate_hex_map_from_pixels


class DetailProcessor:
    def __init__(self, preset: Preset, prefab_manager: PrefabManager):
        self.preset = preset
        self.prefab_manager = prefab_manager

    def process(self, chunk: GenResult, region_context: Region) -> GenResult:
        # Инициализируем поле для объектов, если его нет
        if not hasattr(chunk, 'placed_objects'):
            chunk.placed_objects = []

        # --- ЭТАП 1: Применяем "кисти" для биомов (леса, камни) ---
        # apply_biome_rules(chunk, self.preset, region_context)

        # --- ЭТАП 2: Строим локальные дороги по плану ---
        # build_local_roads(chunk, region_context, self.preset)

        # --- ЭТАП 3: Генерация данных для гексагональной карты сервера ---
        if chunk.grid_spec:
            print(f"  -> Generating server hex map for chunk ({chunk.cx},{chunk.cz})...")
            chunk.hex_map_data = generate_hex_map_from_pixels(
                chunk.grid_spec,
                chunk.layers["surface"],
                chunk.layers["navigation"],
                chunk.layers["height_q"]["grid"]
            )

        chunk.capabilities["has_biomes"] = True
        chunk.capabilities["has_roads"] = True  # Предполагаем, что они могут быть

        return chunk