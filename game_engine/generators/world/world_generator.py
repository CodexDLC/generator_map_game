# game_engine/generators/world/world_generator.py
from __future__ import annotations
from typing import Any, Dict

from .._base.generator import BaseGenerator
from ...core.types import GenResult
from ...story_features import starting_zone_rules
from ...story_features.biome_rules import apply_biome_rules
from ...story_features.local_roads import build_local_roads
from ...world_structure.regions import RegionManager, Region


class WorldGenerator(BaseGenerator):
    def __init__(self, preset: Any, region_manager: RegionManager):
        super().__init__(preset)
        self.region_manager = region_manager

    def generate(self, params: Dict[str, Any]) -> GenResult:
        # Этот метод больше не используется для полной генерации,
        # он будет вызываться из RegionManager для детализации.
        # Оставляем его для обратной совместимости, но основная логика переезжает.
        raise NotImplementedError("Use RegionManager.get_or_create_region instead")

    def finalize_chunk(self, base_result: GenResult, region: Region) -> GenResult:
        """
        НОВЫЙ МЕТОД: Принимает "голый" чанк от BaseGenerator и детализирует его.
        """
        params = {"cx": base_result.cx, "cz": base_result.cz, "seed": base_result.seed}

        # 2. Определяем регион и применяем правила биомов (леса, скалы и т.д.)
        apply_biome_rules(base_result, self.preset, region)

        # 3. Строим дороги, используя глобальный план из региона
        build_local_roads(base_result, self.preset, params, region)

        # 4. Применяем особые правила для стартового города
        if base_result.cx == 0 and 0 <= result.cz <= 3:
            starting_zone_rules.apply_starting_zone_rules(base_result, self.preset)

        return base_result