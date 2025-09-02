# game_engine/story_features/starting_zone_rules.py
from __future__ import annotations
from typing import Any

from ..core.types import GenResult
from ..core.constants import KIND_WATER, KIND_WALL, KIND_GROUND, KIND_SLOPE, KIND_BRIDGE


# ==== utils ====

def _ring_no_south(x: int, z: int, size: int) -> int:
    """Радиус от ближайшей кромки, КРОМЕ южной (юг не трогаем)."""
    return min(x, z, size - 1 - x)

def _city_params(preset):
    elev = getattr(preset, "elevation", {})
    sea = float(elev.get("sea_level_m", 7.0))
    step = float(elev.get("quantization_step_m", 1.0))
    mount = float(elev.get("mountain_level_m", 22.0))
    base = round((sea + (mount - sea) / 2) / step) * step
    return sea, step, base

def flatten_city_base(result: GenResult, base_h: float) -> None:
    """(0,0) выровнять всё в базу как GROUND. Юг будет сохранён логикой колец."""
    if not (result.cx == 0 and result.cz == 0):
        return
    size = result.size
    h = result.layers["height_q"]["grid"]
    k = result.layers["kind"]
    for z in range(size):
        for x in range(size):
            h[z][x] = base_h
            k[z][x] = KIND_GROUND


# ==== геометрия города: вода → банки → стена, мосты только W/E ====

def apply_city_rings(result: GenResult, preset: Any) -> None:
    """
    (0,0):
      r=0..2 → вода
      r=3     → «скала» (+1 шаг от воды)
      r=4     → «скала» (+2 шага)
      r=5..(5+th-1) → стена (+3 шага), с воротами W/E/N
    Южную сторону игнорируем (радиус без южной кромки). Мосты только W/E через воду.
    """
    if not (result.cx == 0 and result.cz == 0):
        return

    size = result.size
    h = result.layers["height_q"]["grid"]
    k = result.layers["kind"]

    sea, step, _base = _city_params(preset)
    water_h = sea - 0.1
    bank1_h = sea + step
    bank2_h = sea + 2 * step
    wall_h  = bank2_h + 3 * step

    wall_cfg = getattr(preset, "city_wall", {}) or {}
    gate_w   = max(1, int(wall_cfg.get("gate_width", 3)))
    wall_th  = max(1, int(wall_cfg.get("thickness", 4)))

    c = size // 2
    a = max(0, c - gate_w // 2)
    b = min(size, a + gate_w)

    # 0..2 вода, 3 и 4 — банки, 5.. — стена
    for z in range(size):
        for x in range(size):
            r = _ring_no_south(x, z, size)

            if 0 <= r <= 2:
                h[z][x] = water_h
                if k[z][x] != KIND_BRIDGE:
                    k[z][x] = KIND_WATER
            elif r == 3:
                h[z][x] = bank1_h
                if k[z][x] == KIND_WATER:
                    k[z][x] = KIND_GROUND
            elif r == 4:
                h[z][x] = bank2_h
                if k[z][x] == KIND_WATER:
                    k[z][x] = KIND_GROUND
            elif 5 <= r < 5 + wall_th:
                h[z][x] = wall_h
                k[z][x] = KIND_WALL
            # r ≥ 5+wall_th остаётся как база из flatten_city_base

    # Ворота W/E/N через всю толщину стены
    r0 = 5
    for d in range(wall_th):
        x_w = r0 + d                   # запад
        x_e = size - 1 - (r0 + d)      # восток
        z_n = r0 + d                   # север
        if 0 <= x_w < size:
            for z in range(a, b):
                k[z][x_w] = KIND_GROUND
        if 0 <= x_e < size:
            for z in range(a, b):
                k[z][x_e] = KIND_GROUND
        if 0 <= z_n < size:
            for x in range(a, b):
                k[z_n][x] = KIND_GROUND

    # Мосты только на воде и только W/E
    slope_cfg = getattr(preset, "slope_obstacles", {}) or {}
    dh = float(slope_cfg.get("delta_h_threshold_m", 3.0))
    bridge_h = water_h + dh

    for d in range(3):  # три внешних радиуса воды
        x_w = 0 + d
        if 0 <= x_w < size:
            for z in range(a, b):
                k[z][x_w] = KIND_BRIDGE
                h[z][x_w] = bridge_h
        x_e = size - 1 - d
        if 0 <= x_e < size:
            for z in range(a, b):
                k[z][x_e] = KIND_BRIDGE
                h[z][x_e] = bridge_h

def create_fortress_slopes(result: GenResult) -> None:
    """Добавить склоны вокруг стены, не трогая остальные склоны базы."""
    size = result.size
    kind = result.layers["kind"]
    original = [row[:] for row in kind]
    for z in range(size):
        for x in range(size):
            if original[z][x] != KIND_GROUND:
                continue
            if (
                (x > 0 and original[z][x-1] == KIND_WALL) or
                (x+1 < size and original[z][x+1] == KIND_WALL) or
                (z > 0 and original[z-1][x] == KIND_WALL) or
                (z+1 < size and original[z+1][x] == KIND_WALL)
            ):
                kind[z][x] = KIND_SLOPE


# ==== оркестратор ====

def apply_starting_zone_rules(result: GenResult, preset: Any) -> None:
    """
    Оркестратор стартовой зоны.
      а) cz==1 и cx∈[-1..1] → сплошная вода (южный океан).
      б) (0,0) → выравнивание базы → кольца/ворота/мосты → склоны у стены.
    Остальные чанки не трогаем.
    """
    cx, cz, size = result.cx, result.cz, result.size
    h = result.layers["height_q"]["grid"]
    k = result.layers["kind"]

    # a) южный океан
    sea, _, base = _city_params(preset)

    # б) только центральный город
    if not (cx == 0 and cz == 0):
        return

    # база
    flatten_city_base(result, base_h=base)

    # кольца + ворота + мосты
    apply_city_rings(result, preset)

    # склоны у стены
    create_fortress_slopes(result)
