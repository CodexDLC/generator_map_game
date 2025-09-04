# game_engine/story_features/starting_zone_rules.py
from __future__ import annotations
from typing import Any

from ..core.types import GenResult
from ..core.constants import (
    KIND_WATER, KIND_WALL, KIND_GROUND, KIND_SLOPE, KIND_BRIDGE
)
from dataclasses import dataclass
from .story_definitions import get_structure_at


@dataclass
class CityParams:
    # (Этот класс остается без изменений)
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


def _apply_walls_and_moat(result: GenResult, p: CityParams, open_sides: list[str] = []):
    """Общая функция для строительства стен, рва и склонов."""
    size = result.size
    h_grid = result.layers["height_q"]["grid"]
    k_grid = result.layers["kind"]
    original_h = [row[:] for row in h_grid]

    for z in range(size):
        for x in range(size):
            # Определяем расстояние до ближайшей "закрытой" стены
            dist_n = z if 'N' not in open_sides else size
            dist_s = size - 1 - z if 'S' not in open_sides else size
            dist_w = x if 'W' not in open_sides else size
            dist_e = size - 1 - x if 'E' not in open_sides else size
            r = min(dist_n, dist_s, dist_w, dist_e)

            ground_h = original_h[z][x]
            if 0 <= r <= p.r_moat_end:
                k_grid[z][x] = KIND_WATER
                h_grid[z][x] = 0.0
            elif r == p.r_slope1 or r == p.r_slope2:
                if k_grid[z][x] == KIND_GROUND: k_grid[z][x] = KIND_SLOPE
            elif p.r_wall_start <= r <= p.r_wall_end:
                k_grid[z][x] = KIND_WALL
                h_grid[z][x] = ground_h + p.wall_height_add
            else:
                k_grid[z][x] = KIND_GROUND

    return original_h



def build_capital_city(result: GenResult, p: CityParams):
    """Столица: 4 стены, гейты на всех сторонах. Без внутренних дорог. + DEBUG-логи."""
    size = result.size
    h_grid = result.layers["height_q"]["grid"]
    k_grid = result.layers["kind"]

    original_h = _apply_walls_and_moat(result, p, open_sides=[])

    c = size // 2
    gate_start = c - p.gate_w // 2
    gate_end = gate_start + p.gate_w

    print(f"[CITY][Capital] size={size}, gates width={p.gate_w}, x_range={gate_start}..{gate_end-1}")

    # Север (z=0)
    north_bridge_rows = list(range(0, p.r_moat_end + 1))
    north_wall_rows   = list(range(p.r_wall_start, p.r_wall_end + 1))
    for x in range(gate_start, gate_end):
        for rz in north_bridge_rows:
            k_grid[rz][x] = KIND_BRIDGE; h_grid[rz][x] = original_h[rz][x]
        for rz in north_wall_rows:
            k_grid[rz][x] = KIND_GROUND; h_grid[rz][x] = original_h[rz][x]
    print(f"[GATE][N] x={gate_start}..{gate_end-1} bridge rows={north_bridge_rows} wall gap rows={north_wall_rows}")

    # Юг (z=size-1)
    z = size - 1
    south_bridge_rows = list(range(z - p.r_moat_end, z + 1))
    south_wall_rows   = list(range(z - p.r_wall_end,  z - p.r_wall_start + 1))
    for x in range(gate_start, gate_end):
        for rz in south_bridge_rows:
            k_grid[rz][x] = KIND_BRIDGE; h_grid[rz][x] = original_h[rz][x]
        for rz in south_wall_rows:
            k_grid[rz][x] = KIND_GROUND;  h_grid[rz][x] = original_h[rz][x]
    print(f"[GATE][S] x={gate_start}..{gate_end-1} bridge rows={south_bridge_rows} wall gap rows={south_wall_rows}")

    # Запад (x=0)
    west_bridge_cols = list(range(0, p.r_moat_end + 1))
    west_wall_cols   = list(range(p.r_wall_start, p.r_wall_end + 1))
    for z in range(gate_start, gate_end):
        for rx in west_bridge_cols:
            k_grid[z][rx] = KIND_BRIDGE; h_grid[z][rx] = original_h[z][rx]
        for rx in west_wall_cols:
            k_grid[z][rx] = KIND_GROUND;  h_grid[z][rx] = original_h[z][rx]
    print(f"[GATE][W] z={gate_start}..{gate_end-1} bridge cols={west_bridge_cols} wall gap cols={west_wall_cols}")

    # Восток (x=size-1)
    x = size - 1
    east_bridge_cols = list(range(x - p.r_moat_end, x + 1))
    east_wall_cols   = list(range(x - p.r_wall_end,  x - p.r_wall_start + 1))
    for z in range(gate_start, gate_end):
        for rx in east_bridge_cols:
            k_grid[z][rx] = KIND_BRIDGE; h_grid[z][rx] = original_h[z][rx]
        for rx in east_wall_cols:
            k_grid[z][rx] = KIND_GROUND;  h_grid[z][rx] = original_h[z][rx]
    print(f"[GATE][E] z={gate_start}..{gate_end-1} bridge cols={east_bridge_cols} wall gap cols={east_wall_cols}")


def apply_starting_zone_rules(result: GenResult, preset: Any) -> None:
    """
    Главный диспетчер. Вызывает правильный строитель для каждого города.
    """
    params = CityParams.from_preset(preset)
    structure = get_structure_at(result.cx, result.cz)
    if not structure:
        return

    print(f"--- Строим '{structure.name}' в чанке ({result.cx}, {result.cz}) ---")

    # --- ГЛАВНОЕ ИЗМЕНЕНИЕ: ВЫБИРАЕМ ФУНКЦИЮ В ЗАВИСИМОСТИ ОТ ИМЕНИ ---
    if structure.name == "Столица":
        build_capital_city(result, params)
    else:
        # Запасной вариант для будущих городов
        build_capital_city(result, params)