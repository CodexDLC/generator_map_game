# game_engine/generators/_base/pregen_rules.py
from __future__ import annotations
from typing import Any, Optional, Tuple, List
import random

from ...core.constants import KIND_WATER

DEBUG_PREG = True
FillDecision = Tuple[str, float]  # (kind, height)


def _pre(preset: Any) -> dict:
    return getattr(preset, "pre_rules", {}) or {}


def early_fill_decision(cx: int, cz: int, size: int, preset: Any, seed: int) -> Optional[FillDecision]:
    """
    Правило океана: все чанки с cz >= cz_min_ocean -> вода.
    Исключение: cz == 0 (нужно для рисования берега).
    """
    elev = getattr(preset, "elevation", {}) or {}
    sea = float(elev.get("sea_level_m", 20.0))
    water_h = sea - 0.1

    ocean = _pre(preset).get("south_ocean", {}) or {}
    cz_min = int(ocean.get("cz_min_ocean", 1))

    if DEBUG_PREG:
        print(f"[PREG] early_fill? cx={cx} cz={cz} cz_min_ocean={cz_min}", flush=True)

    if cz >= cz_min and cz != 0:
        if DEBUG_PREG:
            print(f"[PREG] early_fill=OCEAN cx={cx} cz={cz}", flush=True)
        return (KIND_WATER, water_h)

    if DEBUG_PREG:
        print(f"[PREG] early_fill=NO cx={cx} cz={cz}", flush=True)
    return None


def modify_elevation_inplace(elev_grid: List[List[float]],
                             cx: int, cz: int, size: int, preset: Any, seed: int) -> None:
    """
    Берег рисуем только в ряду cz==0.
    Вода: полоса глубиной 3..10 тайлов (сглаживание по X).
    «Скала» ровно в 1 клетку: ставим её только если перепад с северным соседом >= 2*quantization_step_m.
    Вторую береговую полосу НЕ делаем, чтобы не расширять скалы.
    """
    if cz != 0:
        return

    pre = getattr(preset, "pre_rules", {}) or {}
    cfg = pre.get("cz0_coast", {}) or {}
    dmin = max(1, int(cfg.get("depth_min_tiles", 3)))
    dmax = max(dmin, int(cfg.get("depth_max_tiles", 10)))
    smooth_passes = int(cfg.get("smooth_passes", 1))

    elev = getattr(preset, "elevation", {}) or {}
    sea  = float(elev.get("sea_level_m", 20.0))
    step = float(elev.get("quantization_step_m", 1.0))

    water_h = sea - 0.1
    cliff_h = sea + step              # высота клетки-скалы
    gentle_h = sea + 0.3 * step       # мягкий берег, чтоб не триггерить скалу

    rng = random.Random((seed << 16) ^ (cx << 8) ^ 0x7F4A7C15)

    # случайная глубина воды по X
    depth = [rng.randint(dmin, dmax) for _ in range(size)]

    # сглаживание по X
    for _ in range(max(0, smooth_passes)):
        new = depth[:]
        for x in range(size):
            a = depth[x - 1] if x - 1 >= 0 else depth[x]
            b = depth[x]
            c = depth[x + 1] if x + 1 < size else depth[x]
            new[x] = int(round((a + 2 * b + c) / 4.0))
        depth = new

    H = size
    for x in range(size):
        dep = max(1, min(size, depth[x]))
        z_water_from = max(0, H - dep)
        z_cliff = z_water_from - 1     # ровно одна клетка у кромки

        # вода
        for z in range(z_water_from, H):
            elev_grid[z][x] = water_h

        # решаем, скала это или мягкий берег
        if 0 <= z_cliff < H:
            north_z = z_cliff - 1
            north_h = elev_grid[north_z][x] if north_z >= 0 else gentle_h
            # скала только если перепад >= 2*step
            if (north_h - cliff_h) >= (2.0 * step):
                elev_grid[z_cliff][x] = cliff_h
            else:
                elev_grid[z_cliff][x] = max(elev_grid[z_cliff][x], gentle_h)

