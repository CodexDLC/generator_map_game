# game_engine/generators/world/world_generator.py
from __future__ import annotations
from typing import Any, Dict

from .._base.generator import BaseGenerator
from ...core.types import GenResult
from ...story_features import starting_zone_rules
from ...story_features.biome_rules import apply_biome_rules
from ...story_features.local_roads import build_local_roads  # <<< Импортируем дороги
from ...world_structure.regions import RegionManager


class WorldGenerator(BaseGenerator):
    def __init__(self, preset: Any, region_manager: RegionManager):
        super().__init__(preset)
        self.region_manager = region_manager

    def generate(self, params: Dict[str, Any]) -> GenResult:
        # 1. Создаем базовый ландшафт (высоты, вода, склоны)
        result = super().generate(params)

        # 2. Определяем регион и применяем правила биомов (леса, скалы и т.д.)
        region = self.region_manager.get_region_data(
            *self.region_manager.get_region_coords_from_chunk_coords(result.cx, result.cz)
        )
        apply_biome_rules(result, self.preset, region)

        # --- НАЧАЛО ИЗМЕНЕНИЙ ---
        # 3. Строим дороги. Этот шаг теперь ПОСЛЕДНИЙ перед финализацией.
        build_local_roads(result, self.preset, params)
        # --- КОНЕЦ ИЗМЕНЕНИЙ ---

        # 4. Применяем особые правила для стартовой зоны (например, город)
        is_starting_zone = (
                params.get("world_id") == "world_location" and
                -1 <= result.cx <= 1 and
                -1 <= result.cz <= 1
        )
        if is_starting_zone:
            starting_zone_rules.apply_starting_zone_rules(result, self.preset)

        return result