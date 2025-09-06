# game_engine/generators/_base/pregen_rules.py
from __future__ import annotations
import random
from typing import Any, Optional, Tuple

from ...core.constants import (
    NAV_WATER, NAV_OBSTACLE, KIND_GROUND, KIND_SAND, KIND_SLOPE
)

FillDecision = Tuple[str, float]


def early_fill_decision(cx: int, cz: int, size: int, preset: Any, seed: int) -> Optional[FillDecision]:
    ocean_cfg = getattr(preset, "pre_rules", {}).get("south_ocean", {})
    cz_min = int(ocean_cfg.get("cz_min_ocean", 1))
    if cz >= cz_min:
        return NAV_WATER, 0.0
    return None


def apply_ocean_coast_rules(result: Any, preset: Any):
    """
    Создает сложную, красивую береговую линию на чанках, граничащих с океаном.
    """
    # --- ГЛАВНОЕ ИСПРАВЛЕНИЕ: Правильное условие для береговой линии ---
    # Правило должно применяться к чанкам на границе суши и океана (cz=0)
    ocean_cfg = getattr(preset, "pre_rules", {}).get("south_ocean", {})
    coastline_cz = int(ocean_cfg.get("cz_min_ocean", 1)) - 1

    if result.cz != coastline_cz:
        return
    # --- КОНЕЦ ИСПРАВЛЕНИЯ ---

    size = result.size
    surface_grid = result.layers["surface"]
    nav_grid = result.layers["navigation"]
    h_grid = result.layers["height_q"]["grid"]

    cfg = getattr(preset, "pre_rules", {}).get("cz0_coast", {})
    dmin = max(1, int(cfg.get("depth_min_tiles", 8)))
    dmax = max(dmin, int(cfg.get("depth_max_tiles", 20)))
    smooth_passes = int(cfg.get("smooth_passes", 4))
    elev_cfg = getattr(preset, "elevation", {})
    sea_level = float(elev_cfg.get("sea_level_m", 12.0))
    step = float(elev_cfg.get("quantization_step_m", 1.0))
    water_h = sea_level - step
    rng = random.Random((result.seed << 16) ^ (result.cx << 8) ^ 0x7F4A7C15)

    depth = [rng.randint(dmin, dmax) for _ in range(size)]
    for _ in range(smooth_passes):
        new = depth[:];
        for x in range(1, size - 1): new[x] = int(round((depth[x - 1] + 2 * depth[x] + depth[x + 1]) / 4.0))
        depth = new

    for x in range(size):
        water_depth_here = max(1, min(size, depth[x]))
        z_water_from = max(0, size - water_depth_here)
        for z in range(z_water_from, size):
            surface_grid[z][x] = KIND_SAND
            nav_grid[z][x] = NAV_WATER
            h_grid[z][x] = water_h

    new_surface_grid = [row[:] for row in surface_grid]
    for z in range(1, size - 1):
        for x in range(1, size - 1):
            if surface_grid[z][x] == KIND_GROUND:
                is_on_coast = False
                for dx, dz in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                    if nav_grid[z + dz][x + dx] == NAV_WATER:
                        is_on_coast = True
                        break
                if is_on_coast:
                    if abs(h_grid[z][x] - water_h) < step:
                        new_surface_grid[z][x] = KIND_SAND
                    else:
                        new_surface_grid[z][x] = KIND_SLOPE

    result.layers["surface"] = new_surface_grid

    coast_width = dmax + smooth_passes
    start_z = max(0, size - coast_width)
    for z in range(start_z, size):
        for x in range(size):
            if nav_grid[z][x] == NAV_WATER:
                progress = (z - start_z) / (coast_width - 1) if coast_width > 1 else 1.0
                h_grid[z][x] = water_h * (1 - progress)