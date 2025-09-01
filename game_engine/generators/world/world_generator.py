# engine/worldgen_core/world/world_generator.py
from __future__ import annotations
from typing import Any, Dict

from ..base.generator import BaseGenerator, GenResult
from engine.worldgen_core.pathfinding_ai.local_roads import build_local_roads
from ..story_features import starting_zone_rules
# <<< НОВЫЙ ИМПОРТ >>>
from ..grid_alg.terrain import classify_terrain, apply_slope_obstacles


class WorldGenerator(BaseGenerator):
    """
    Генератор мира, который сначала создает базовый процедурный ландшафт,
    а затем накладывает на него "сценарные" объекты и пересчитывает рельеф.
    """

    def generate(self, params: Dict[str, Any]) -> GenResult:
        # 1. Получаем "сырой" процедурный чанк (с уже посчитанными склонами для исходного рельефа)
        result = super().generate(params)

        # 2. Передаем его в модуль сценарных правил для модификации (добавляется стена и океан)
        if params.get("world_id") == "world_location":
            starting_zone_rules.apply_starting_zone_rules(result, self.preset)

        # 3. <<< КЛЮЧЕВОЕ ИСПРАВЛЕНИЕ >>>
        # После того как стена изменила карту высот, нам нужно
        # заново классифицировать тайлы (чтобы стена не считалась "землей")
        # и заново рассчитать склоны. Это создаст правильные склоны у подножия стены.
        classify_terrain(result.layers["height_q"]["grid"], result.layers["kind"], self.preset)
        apply_slope_obstacles(result.layers["height_q"]["grid"], result.layers["kind"], self.preset)
        # <<< КОНЕЦ ИСПРАВЛЕНИЯ >>>

        # 4. Прокладываем дороги по финальному, полностью готовому ландшафту
        paths = build_local_roads(result.layers["kind"], result.layers["height_q"]["grid"],
                                  result.size, self.preset, params, width=2)
        if paths:
            result.layers["roads"] = paths

        return result