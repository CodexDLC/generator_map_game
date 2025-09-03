# game_engine/generators/_base/pregen_rules.py
from __future__ import annotations

import random
# --- НАЧАЛО ИЗМЕНЕНИЯ: Добавляем импорты для определения типов ---
from typing import Any, Optional, Tuple
# --- КОНЕЦ ИЗМЕНЕНИЯ ---

from ...core.constants import KIND_WATER, KIND_GROUND, KIND_SAND, KIND_SLOPE

# --- НАЧАЛО ИЗМЕНЕНИЯ: Определяем недостающий тип ---
FillDecision = Tuple[str, float]  # (kind, height)


# --- КОНЕЦ ИЗМЕНЕНИЯ ---


def early_fill_decision(cx: int, cz: int, size: int, preset: Any, seed: int) -> Optional[FillDecision]:
    """Правило океана: все чанки с cz >= 1 заливаются водой с высотой 0."""
    ocean_cfg = getattr(preset, "pre_rules", {}).get("south_ocean", {})
    cz_min = int(ocean_cfg.get("cz_min_ocean", 1))

    if cz >= cz_min:
        # Океан вдали от берега сразу имеет высоту 0 для будущих рек
        return KIND_WATER, 0.0
    return None


def apply_ocean_coast_rules(result: Any, preset: Any):
    """
    Создает сложную, красивую береговую линию на чанках cz=0.
    1. Генерирует изломанный берег.
    2. Расставляет пляжи и склоны.
    3. Углубляет воду к южному краю до высоты 0.
    """
    if result.cz != 3:
        return

    size = result.size
    k_grid = result.layers["kind"]
    h_grid = result.layers["height_q"]["grid"]

    # --- Шаг 1: Генерируем случайную, изломанную береговую линию ---

    cfg = getattr(preset, "pre_rules", {}).get("cz0_coast", {})
    dmin = max(1, int(cfg.get("depth_min_tiles", 8)))
    dmax = max(dmin, int(cfg.get("depth_max_tiles", 20)))
    smooth_passes = int(cfg.get("smooth_passes", 4))

    elev_cfg = getattr(preset, "elevation", {})
    sea_level = float(elev_cfg.get("sea_level_m", 12.0))
    step = float(elev_cfg.get("quantization_step_m", 1.0))

    # Начальная высота воды у берега
    water_h = sea_level - step

    rng = random.Random((result.seed << 16) ^ (result.cx << 8) ^ 0x7F4A7C15)

    depth = [rng.randint(dmin, dmax) for _ in range(size)]
    for _ in range(smooth_passes):
        new = depth[:]
        for x in range(1, size - 1):
            new[x] = int(round((depth[x - 1] + 2 * depth[x] + depth[x + 1]) / 4.0))
        depth = new

    for x in range(size):
        water_depth_here = max(1, min(size, depth[x]))
        z_water_from = max(0, size - water_depth_here)
        for z in range(z_water_from, size):
            # Ставим воду и ее начальную высоту
            k_grid[z][x] = KIND_WATER
            h_grid[z][x] = water_h

    # --- Шаг 2: Расставляем пляжи и склоны ---

    new_k_grid = [row[:] for row in k_grid]
    for z in range(1, size - 1):
        for x in range(1, size - 1):
            if k_grid[z][x] == KIND_GROUND:
                is_on_coast = False
                for dx, dz in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                    if k_grid[z + dz][x + dx] == KIND_WATER:
                        is_on_coast = True
                        break

                if is_on_coast:
                    if abs(h_grid[z][x] - water_h) < step:
                        new_k_grid[z][x] = KIND_SAND
                    else:
                        new_k_grid[z][x] = KIND_SLOPE

    result.layers["kind"] = new_k_grid

    # --- Шаг 3: Углубляем воду к южному краю ---

    coast_width = dmax + smooth_passes
    start_z = max(0, size - coast_width)

    for z in range(start_z, size):
        for x in range(size):
            if result.layers["kind"][z][x] == KIND_WATER:
                if coast_width <= 1:
                    progress = 1.0
                else:
                    progress = (z - start_z) / (coast_width - 1)

                h_grid[z][x] = water_h * (1 - progress)