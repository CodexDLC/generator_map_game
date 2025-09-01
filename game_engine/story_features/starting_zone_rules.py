# engine/worldgen_core/story_features/starting_zone_rules.py
from __future__ import annotations
from typing import Any

from ..base.types import GenResult
from ..base.constants import KIND_WATER, KIND_WALL, KIND_GROUND


def apply_starting_zone_rules(result: GenResult, preset: Any):
    """
    Накладывает на сгенерированный чанк специальные правила для стартовой зоны.
    - Строит стену вокруг чанка (0,0) с башнями и воротами.
    - Соседние чанки достраивают свои сегменты стены.
    - Южные чанки превращаются в воду для порта.
    """
    cx, cz, size = result.cx, result.cz, result.size
    kind_grid = result.layers["kind"]
    height_grid = result.layers["height_q"]["grid"]

    # 1. Загружаем настройки стены из пресета
    city_wall_cfg = getattr(preset, "city_wall", {})
    if not city_wall_cfg.get("enabled", False):
        return  # Если стена выключена, выходим

    wall_thickness = int(city_wall_cfg.get("thickness", 2))  # По умолчанию 2
    gate_width = int(city_wall_cfg.get("gate_width", 3))  # По умолчанию 3
    tower_size = int(city_wall_cfg.get("tower_size", 4))  # По умолчанию 4
    wall_height = float(preset.elevation.get("mountain_level_m", 22.0))

    mid = size // 2
    gate_half = gate_width // 2

    def build_wall_segment(x_range, z_range):
        for z in z_range:
            for x in x_range:
                if 0 <= x < size and 0 <= z < size:
                    kind_grid[z][x] = KIND_WALL
                    height_grid[z][x] = wall_height

    def carve_gate_segment(x_range, z_range):
        # Используем исходные высоты для ворот, чтобы не создавать обрывы
        original_heights = [row[:] for row in result.layers["height_q"]["grid"]]
        for z in z_range:
            for x in x_range:
                if 0 <= x < size and 0 <= z < size:
                    kind_grid[z][x] = KIND_GROUND
                    height_grid[z][x] = original_heights[z][x]

    # --- Правило 1: Южный Океан ---
    if cz == 1 and -1 <= cx <= 1:
        sea_level = float(preset.elevation.get("sea_level_m", 7.0))
        for z in range(size):
            for x in range(size):
                height_grid[z][x] = sea_level - 1.0
                kind_grid[z][x] = KIND_WATER
        return  # Этот чанк - вода, стена тут не нужна

    # --- Правило 2: Строительство стены по частям ---

    # Центральный чанк (0, 0) - строит 3 стены, 2 башни и 3 ворот
    if cx == 0 and cz == 0:
        # Северная стена
        build_wall_segment(range(0, size), range(0, wall_thickness))
        # Западная стена
        build_wall_segment(range(0, wall_thickness), range(wall_thickness, size))
        # Восточная стена
        build_wall_segment(range(size - wall_thickness, size), range(wall_thickness, size))

        # Башни
        build_wall_segment(range(0, tower_size), range(0, tower_size))  # Северо-западная
        build_wall_segment(range(size - tower_size, size), range(0, tower_size))  # Северо-восточная

        # Ворота
        carve_gate_segment(range(mid - gate_half, mid + gate_half + 1), range(0, wall_thickness))  # Северные
        carve_gate_segment(range(0, wall_thickness), range(mid - gate_half, mid + gate_half + 1))  # Западные
        carve_gate_segment(range(size - wall_thickness, size), range(mid - gate_half, mid + gate_half + 1))  # Восточные

    # Северный чанк (0, -1) - достраивает северную стену
    elif cx == 0 and cz == -1:
        build_wall_segment(range(0, size), range(size - wall_thickness, size))

    # Западный чанк (-1, 0) - достраивает западную стену
    elif cx == -1 and cz == 0:
        build_wall_segment(range(size - wall_thickness, size), range(0, size))

    # Восточный чанк (1, 0) - достраивает восточную стену
    elif cx == 1 and cz == 0:
        build_wall_segment(range(0, wall_thickness), range(0, size))

    # Северо-западный чанк (-1, -1) - строит угол
    elif cx == -1 and cz == -1:
        build_wall_segment(range(size - wall_thickness, size), range(0, size))  # Восточный сегмент
        build_wall_segment(range(0, size - wall_thickness), range(size - wall_thickness, size))  # Южный сегмент

    # Северо-восточный чанк (1, -1) - строит угол
    elif cx == 1 and cz == -1:
        build_wall_segment(range(0, wall_thickness), range(0, size))  # Западный сегмент
        build_wall_segment(range(wall_thickness, size), range(size - wall_thickness, size))  # Южный сегмент