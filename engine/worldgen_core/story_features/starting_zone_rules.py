# engine/worldgen_core/story_features/starting_zone_rules.py
from __future__ import annotations
from typing import Any

from ..base.types import GenResult
from ..base.constants import KIND_WATER, KIND_WALL, KIND_GROUND


def apply_starting_zone_rules(result: GenResult, preset: Any):
    """
    Накладывает на сгенерированный чанк специальные правила, если он
    входит в стартовую зону 3x3.
    """
    cx, cz, size = result.cx, result.cz, result.size

    # --- Правило 1: Южный Океан ---
    if cz == 1 and -1 <= cx <= 1:
        sea_level = float(preset.elevation.get("sea_level_m", 7.0))
        for z in range(size):
            for x in range(size):
                result.layers["height_q"]["grid"][z][x] = sea_level - 1.0
                result.layers["kind"][z][x] = KIND_WATER

    # --- Правило 2: Городская Стена ---

    # <<< НАЧАЛО ИЗМЕНЕНИЙ >>>

    # 1. Загружаем настройки стены из пресета.
    #    getattr(preset, "city_wall", {}) безопасно вернет пустой словарь, если секции нет.
    city_wall_cfg = getattr(preset, "city_wall", {})

    # 2. ПРОВЕРЯЕМ, включена ли вообще стена в пресете.
    if not city_wall_cfg.get("enabled", False):
        return  # Если стена выключена, просто выходим.

    # 3. Используем значения из пресета, а не жестко заданные константы.
    wall_thickness = int(city_wall_cfg.get("thickness", 3))
    gate_width = int(city_wall_cfg.get("gate_width", 3))

    # <<< КОНЕЦ ИЗМЕНЕНИЙ >>>

    wall_height = float(preset.elevation.get("mountain_level_m", 22.0))
    mid = size // 2
    gate_half = gate_width // 2

    kind_grid = result.layers["kind"]
    height_grid = result.layers["height_q"]["grid"]

    def build_wall_segment(x_range, z_range):
        for z in z_range:
            for x in x_range:
                kind_grid[z][x] = KIND_WALL
                height_grid[z][x] = wall_height

    original_heights = [row[:] for row in height_grid]

    def carve_gate_segment(x_range, z_range):
        for z in z_range:
            for x in x_range:
                kind_grid[z][x] = KIND_GROUND
                height_grid[z][x] = original_heights[z][x]

    # --- Логика постройки стены остается той же, но теперь использует переменные из пресета ---

    # Северная стена: строится в чанках (-1,-1), (0,-1), (1,-1)
    if cz == -1 and -1 <= cx <= 1:
        build_wall_segment(range(size), range(wall_thickness))
        if cx == 0:
            carve_gate_segment(range(mid - gate_half, mid + gate_half + 1), range(wall_thickness))

    # Южная стена: строится в чанках (-1,0), (0,0), (1,0)
    if cz == 0 and -1 <= cx <= 1:
        build_wall_segment(range(size), range(size - wall_thickness, size))

    # Западная стена: строится в чанках (-1,-1), (-1,0)
    if cx == -1 and -1 <= cz <= 0:
        build_wall_segment(range(wall_thickness), range(size))
        if cz == 0:
            carve_gate_segment(range(wall_thickness), range(mid - gate_half, mid + gate_half + 1))

    # Восточная стена: строится в чанках (1,-1), (1,0)
    if cx == 1 and -1 <= cz <= 0:
        build_wall_segment(range(size - wall_thickness, size), range(size))
        if cz == 0:
            carve_gate_segment(range(size - wall_thickness, size), range(mid - gate_half, mid + gate_half + 1))