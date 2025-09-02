# game_engine/story_features/starting_zone_rules.py
from __future__ import annotations
from typing import Any
from dataclasses import dataclass

from ..core.types import GenResult
from ..core.constants import (
    KIND_WATER, KIND_WALL, KIND_GROUND, KIND_SLOPE, KIND_BRIDGE, KIND_OBSTACLE
)


@dataclass
class CityParams:
    """Хранит все рассчитанные параметры для строительства города."""
    sea_level: float
    step: float
    mountain_level: float
    gate_w: int
    wall_th: int
    r_moat_end: int
    r_slope1: int
    r_slope2: int
    r_wall_start: int
    r_wall_end: int
    base_h: float
    water_h: float
    slope1_h: float
    slope2_h: float
    wall_h: float

    @classmethod
    def from_preset(cls, preset: Any) -> "CityParams":
        """Фабричный метод для создания параметров из пресета."""
        elev = getattr(preset, "elevation", {})
        sea_level = float(elev.get("sea_level_m", 7.0))
        step = float(elev.get("quantization_step_m", 1.0))
        mountain_level = float(elev.get("mountain_level_m", 22.0))
        base_h = round((sea_level + (mountain_level - sea_level) / 2) / step) * step

        wall_cfg = getattr(preset, "city_wall", {}) or {}
        wall_th = max(1, int(wall_cfg.get("thickness", 4)))

        r_moat_end = 2
        r_slope1 = 3
        r_slope2 = 4
        r_wall_start = 5

        return cls(
            sea_level=sea_level,
            step=step,
            mountain_level=mountain_level,
            gate_w=max(1, int(wall_cfg.get("gate_width", 3))),
            wall_th=wall_th,
            r_moat_end=r_moat_end,
            r_slope1=r_slope1,
            r_slope2=r_slope2,
            r_wall_start=r_wall_start,
            r_wall_end=r_wall_start + wall_th - 1,
            base_h=base_h,
            water_h=sea_level - 0.1,
            slope1_h=sea_level + step,
            slope2_h=sea_level + 2 * step,
            wall_h=mountain_level - step
        )


def build_city_base_and_walls(result: GenResult, p: CityParams):
    """Этап 1: Строит основу города, стены, рвы, адаптируясь к скалам."""
    size = result.size
    h_grid = result.layers["height_q"]["grid"]
    k_grid = result.layers["kind"]
    original_h = [row[:] for row in h_grid]

    for z in range(size):
        for x in range(size):
            r = min(x, z, size - 1 - x)
            is_natural_cliff = original_h[z][x] >= p.mountain_level

            if 0 <= r <= p.r_moat_end:
                if is_natural_cliff:
                    k_grid[z][x] = KIND_OBSTACLE
                else:
                    k_grid[z][x] = KIND_WATER; h_grid[z][x] = p.water_h
            elif r == p.r_slope1:
                if is_natural_cliff:
                    k_grid[z][x] = KIND_OBSTACLE
                else:
                    k_grid[z][x] = KIND_SLOPE; h_grid[z][x] = p.slope1_h
            elif r == p.r_slope2:
                if is_natural_cliff:
                    k_grid[z][x] = KIND_OBSTACLE
                else:
                    k_grid[z][x] = KIND_SLOPE; h_grid[z][x] = p.slope2_h
            elif p.r_wall_start <= r <= p.r_wall_end:
                if is_natural_cliff:
                    k_grid[z][x] = KIND_OBSTACLE
                else:
                    k_grid[z][x] = KIND_WALL; h_grid[z][x] = p.wall_h
            else:
                k_grid[z][x] = KIND_GROUND;
                h_grid[z][x] = p.base_h

    result.metrics["temp_original_h"] = original_h


def create_fortress_slopes(result: GenResult) -> None:
    """Этап 2: Добавляет склоны к искусственным стенам."""
    size = result.size
    kind = result.layers["kind"]
    original = [row[:] for row in kind]
    for z in range(size):
        for x in range(size):
            if original[z][x] != KIND_GROUND: continue
            if ((x > 0 and original[z][x - 1] == KIND_WALL) or
                    (x + 1 < size and original[z][x + 1] == KIND_WALL) or
                    (z > 0 and original[z - 1][x] == KIND_WALL) or
                    (z + 1 < size and original[z + 1][x] == KIND_WALL)):
                kind[z][x] = KIND_SLOPE


def carve_city_entrances(result: GenResult, p: CityParams):
    """Этап 3: Прорезает ворота и дороги поверх готового рельефа."""
    size = result.size
    h_grid = result.layers["height_q"]["grid"]
    k_grid = result.layers["kind"]
    original_h = result.metrics.get("temp_original_h", [])

    c = size // 2
    gate_start = max(0, c - p.gate_w // 2)
    gate_end = min(size, gate_start + p.gate_w)

    if original_h:
        is_north_gate_blocked = any(
            original_h[r][x] >= p.mountain_level for r in range(p.r_wall_end + 1) for x in range(gate_start, gate_end))
        if not is_north_gate_blocked:
            for r in range(p.r_wall_end + 1):
                for x in range(gate_start, gate_end):
                    k_grid[r][x] = KIND_GROUND;
                    h_grid[r][x] = p.base_h

    road_extension_inner = 10
    total_road_length = p.r_wall_end + 1 + road_extension_inner
    for z in range(gate_start, gate_end):
        for i in range(total_road_length):
            x_w = i
            if 0 <= x_w < size:
                h_grid[z][x_w] = p.base_h
                k_grid[z][x_w] = KIND_BRIDGE if x_w <= p.r_moat_end else KIND_GROUND
            x_e = size - 1 - i
            if 0 <= x_e < size:
                h_grid[z][x_e] = p.base_h
                k_grid[z][x_e] = KIND_BRIDGE if (size - 1 - x_e) <= p.r_moat_end else KIND_GROUND


def apply_starting_zone_rules(result: GenResult, preset: Any) -> None:
    """Оркестратор: вызывает этапы генерации города в правильном порядке."""
    if not (result.cx == 0 and result.cz == 0):
        return

    city_params = CityParams.from_preset(preset)
    build_city_base_and_walls(result, city_params)
    create_fortress_slopes(result)
    carve_city_entrances(result, city_params)