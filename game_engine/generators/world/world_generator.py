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
        region = self.region_manager.get_region(
            result.cx, result.cz
        )
        apply_biome_rules(result, self.preset, region)

        # 3. Строим дороги, передавая ВЕСЬ РЕГИОН с планом дорог
        build_local_roads(result, self.preset, params, region)

        # 4. Применяем особые правила для стартового города ТОЛЬКО в чанке (0,0)
        if result.cx == 0 and 0 <= result.cz <= 3:
            starting_zone_rules.apply_starting_zone_rules(result, self.preset)

        # Эта строка должна быть на этом уровне отступа, вне блока if
        return result