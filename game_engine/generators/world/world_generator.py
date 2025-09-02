# game_engine/generators/world/world_generator.py
from __future__ import annotations
from typing import Any, Dict

from .._base.generator import BaseGenerator
from ...core.types import GenResult
from ...story_features import starting_zone_rules
from ...algorithms.terrain.terrain import apply_slope_obstacles


class WorldGenerator(BaseGenerator):
    def generate(self, params: Dict[str, Any]) -> GenResult:
        result = super().generate(params)

        # Проверяем, что это мир 'world_location' И чанк находится в стартовой зоне 3x3
        is_starting_zone = (
                params.get("world_id") == "world_location" and
                -1 <= params.get("cx", 99) <= 1 and
                -1 <= params.get("cz", 99) <= 1
        )

        if is_starting_zone:
            starting_zone_rules.apply_starting_zone_rules(result, self.preset)

        else:
            # Для всех остальных чанков мира используем стандартный расчет склонов
            apply_slope_obstacles(result.layers["height_q"]["grid"], result.layers["kind"], self.preset)


        # 4. Прокладка дорог (пока отключаем)
        # paths = build_local_roads(...)
        # if paths:
        #    result.layers["roads"] = paths

        return result