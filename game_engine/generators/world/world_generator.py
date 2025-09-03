# game_engine/generators/world/world_generator.py
from __future__ import annotations
from typing import Any, Dict

from .._base.generator import BaseGenerator
from ...core.types import GenResult
from ...story_features import starting_zone_rules
from ...story_features.biome_rules import apply_biome_rules
from ...story_features.features import generate_forests, generate_rocks
from ...story_features.local_roads import build_local_roads  # <<< ДОБАВЛЕНО
from ...world_structure.regions import RegionManager


class WorldGenerator(BaseGenerator):
    def __init__(self, preset: Any, region_manager: RegionManager):
        super().__init__(preset)
        self.region_manager = region_manager

    def generate(self, params: Dict[str, Any]) -> GenResult:
        # 1. Создаем базовый ландшафт (высоты, вода, склоны)
        result = super().generate(params)

        # 2. Получаем данные о биоме, чтобы передать их дальше
        region = self.region_manager.get_region_data(
            *self.region_manager.get_region_coords_from_chunk_coords(result.cx, result.cz)
        )

        # 3. Применяем правила биома (фабрика)
        apply_biome_rules(result, self.preset, region)

        # 4. Рисуем леса и камни
        generate_forests(result, self.preset, region)
        generate_rocks(result, self.preset)

        # <<< ВРЕМЕННО: Рисуем дороги после всех объектов >>>
        # Функция build_local_roads использует kind и height для прокладки пути.
        # Поэтому она должна быть вызвана после того, как эти слои будут заполнены.
        build_local_roads(
            result.layers["kind"],
            result.layers["height_q"]["grid"],
            result.size,
            self.preset,
            params
        )

        is_starting_zone = (
                params.get("world_id") == "world_location" and
                -1 <= result.cx <= 1 and
                -1 <= result.cz <= 1
        )
        if is_starting_zone:
            starting_zone_rules.apply_starting_zone_rules(result, self.preset)

        return result