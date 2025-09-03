# game_engine/story_features/starting_zone_rules.py
from __future__ import annotations
from typing import Any

from ..core.types import GenResult
from ..core.constants import (
    KIND_WATER, KIND_WALL, KIND_GROUND, KIND_SLOPE, KIND_BRIDGE, KIND_OBSTACLE
)
from dataclasses import dataclass


# CityParams остается таким же
@dataclass
class CityParams:
    # ... (содержимое класса CityParams без изменений) ...
    step: float
    gate_w: int
    wall_th: int
    r_moat_end: int
    r_slope1: int
    r_slope2: int
    r_wall_start: int
    r_wall_end: int
    wall_height_add: float

    @classmethod
    def from_preset(cls, preset: Any) -> "CityParams":
        elev = getattr(preset, "elevation", {})
        wall_cfg = getattr(preset, "city_wall", {}) or {}
        wall_th = max(1, int(wall_cfg.get("thickness", 4)))
        return cls(
            step=float(elev.get("quantization_step_m", 1.0)),
            gate_w=max(1, int(wall_cfg.get("gate_width", 3))),
            wall_th=wall_th,
            r_moat_end=2,
            r_slope1=3,
            r_slope2=4,
            r_wall_start=5,
            r_wall_end=5 + wall_th - 1,
            wall_height_add=10.0
        )


# --- ИСПРАВЛЕННАЯ СТОЛИЦА В (0, 0) ---
def build_capital_city(result: GenResult, p: CityParams):
    """Строит столицу с 4-мя гарантированными выходами."""
    size = result.size
    h_grid = result.layers["height_q"]["grid"]
    k_grid = result.layers["kind"]
    original_h = [row[:] for row in h_grid]

    # Строим стены, ров и склоны (как и раньше)
    for z in range(size):
        for x in range(size):
            r = min(x, z, size - 1 - x, size - 1 - z)
            ground_h = original_h[z][x]
            if 0 <= r <= p.r_moat_end:
                k_grid[z][x] = KIND_WATER;
                h_grid[z][x] = 0.0
            elif r == p.r_slope1 or r == p.r_slope2:
                if k_grid[z][x] == KIND_GROUND: k_grid[z][x] = KIND_SLOPE
            elif p.r_wall_start <= r <= p.r_wall_end:
                k_grid[z][x] = KIND_WALL;
                h_grid[z][x] = ground_h + p.wall_height_add

    # --- УПРОЩЕННАЯ И ИСПРАВЛЕННАЯ ЛОГИКА ВОРОТ ---
    c = size // 2
    gate_start = c - p.gate_w // 2
    gate_end = gate_start + p.gate_w

    # Прорезаем горизонтальную дорогу (Запад-Восток)
    for z in range(gate_start, gate_end):
        for x in range(size):
            h_grid[z][x] = original_h[z][x]
            is_over_moat = (x <= p.r_moat_end or size - 1 - x <= p.r_moat_end)
            k_grid[z][x] = KIND_BRIDGE if is_over_moat and h_grid[z][x] > 0 else KIND_GROUND

    # Прорезаем вертикальную дорогу (Север-Юг)
    for x in range(gate_start, gate_end):
        for z in range(size):
            h_grid[z][x] = original_h[z][x]
            is_over_moat = (z <= p.r_moat_end or size - 1 - z <= p.r_moat_end)
            k_grid[z][x] = KIND_BRIDGE if is_over_moat and h_grid[z][x] > 0 else KIND_GROUND


# --- ИСПРАВЛЕННЫЙ ПОРТОВЫЙ ГОРОД В (0, 3) ---
def build_port_city(result: GenResult, p: CityParams):
    """Строит портовый город БЕЗ ЮЖНОЙ и СЕВЕРНОЙ стены/дороги."""
    size = result.size
    h_grid = result.layers["height_q"]["grid"]
    k_grid = result.layers["kind"]
    base_h = 15.0

    for z in range(size):
        for x in range(size):
            r = min(x, z, size - 1 - x)
            is_south_wall_zone = (p.r_wall_start <= (size - 1 - z) <= p.r_wall_end)
            if is_south_wall_zone:
                k_grid[z][x] = KIND_GROUND;
                h_grid[z][x] = base_h
                continue
            if 0 <= r <= p.r_moat_end:
                k_grid[z][x] = KIND_WATER;
                h_grid[z][x] = base_h - p.step * 4
            elif r == p.r_slope1:
                k_grid[z][x] = KIND_SLOPE;
                h_grid[z][x] = base_h - p.step * 2
            elif r == p.r_slope2:
                k_grid[z][x] = KIND_SLOPE;
                h_grid[z][x] = base_h - p.step
            elif p.r_wall_start <= r <= p.r_wall_end:
                k_grid[z][x] = KIND_WALL;
                h_grid[z][x] = base_h + p.step * 5
            else:
                k_grid[z][x] = KIND_GROUND;
                h_grid[z][x] = base_h

    c = size // 2
    gate_start = c - p.gate_w // 2
    gate_end = gate_start + p.gate_w

    # Прорезаем ТОЛЬКО горизонтальную дорогу (Запад-Восток)
    for z in range(gate_start, gate_end):
        for x in range(size):
            h_grid[z][x] = base_h
            is_over_moat = (x <= p.r_moat_end or size - 1 - x <= p.r_wall_end)
            k_grid[z][x] = KIND_BRIDGE if is_over_moat else KIND_GROUND

# --- ГЛАВНАЯ ФУНКЦИЯ-ДИСПЕТЧЕР (без изменений) ---
def apply_starting_zone_rules(result: GenResult, preset: Any) -> None:
    params = CityParams.from_preset(preset)
    if result.cx == 0 and result.cz == 0:
        print(f"--- Строим СТОЛИЦУ в чанке ({result.cx}, {result.cz}) ---")
        build_capital_city(result, params)
    elif result.cx == 0 and result.cz == 3:
        print(f"--- Строим ПОРТОВЫЙ ГОРОД в чанке ({result.cx}, {result.cz}) ---")
        build_port_city(result, params)