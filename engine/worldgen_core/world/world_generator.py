# engine/worldgen_core/world/world_generator.py
from __future__ import annotations
from typing import Any, Dict

from ..base.generator import BaseGenerator, GenResult
from engine.worldgen_core.pathfinding_ai.local_roads import build_local_roads

class WorldGenerator(BaseGenerator):
    """
    Генератор мира, отвечающий за создание высокоуровневых сущностей,
    таких как биомы, реки, города и т.д.

    Наследует всю базовую логику (ландшафт, порты, связность) от BaseGenerator.
    """

    def generate(self, params: Dict[str, Any]) -> GenResult:
        # 1. Получаем полностью готовый к использованию "базовый" чанк
        result = super().generate(params)

        paths = build_local_roads(result.layers["kind"], result.layers["height_q"]["grid"],
                                  result.size, self.preset, params, width=2)  # width по желанию
        if paths:
            result.layers["roads"] = paths  # чтобы видеть/отлаживать маршруты

        # 2. <<< ЗДЕСЬ НАЧНЕТСЯ БУДУЩАЯ ЛОГИКА >>>
        # Например:
        #   - Определить биом для этого чанка (cx, cz)
        #   - В зависимости от биома, изменить параметры шума
        #   - Разместить на карте реки, леса, скалы и т.д.
        #   - ...

        # 3. Возвращаем модифицированный результат
        return result