# game_engine/story_features/starting_zone_rules.py
from __future__ import annotations
from typing import Any

from ..core.types import GenResult

# --- ИЗМЕНЕНИЕ: Импортируем новые константы ---
from ..core.constants import (
    NAV_WATER,
    NAV_BRIDGE,
    KIND_GROUND,
    KIND_SLOPE,
    KIND_SAND,
    KIND_ROAD,
)
from dataclasses import dataclass
from .story_definitions import get_structure_at


@dataclass
class CityParams:
    # (Этот класс остается без изменений, но wall_... параметры больше не используются)
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
            wall_height_add=10.0,
        )


def _apply_moat_and_slopes(result: GenResult, p: CityParams):
    """
    Общая функция для строительства рва и склонов (стены удалены).
    """
    size = result.size
    h_grid = result.layers["height_q"]["grid"]
    surface_grid = result.layers["surface"]
    nav_grid = result.layers["navigation"]

    for z in range(size):
        for x in range(size):
            dist_n, dist_s = z, size - 1 - z
            dist_w, dist_e = x, size - 1 - x
            r = min(dist_n, dist_s, dist_w, dist_e)

            if 0 <= r <= p.r_moat_end:
                surface_grid[z][x] = KIND_SAND  # Дно рва - песок
                nav_grid[z][x] = NAV_WATER  # Ров непроходим (это вода)
                h_grid[z][x] = 0.0  # Ров имеет нулевую высоту
            elif r == p.r_slope1 or r == p.r_slope2:
                if surface_grid[z][x] == KIND_GROUND:
                    surface_grid[z][x] = KIND_SLOPE  # Берега рва - склоны


def build_capital_city(result: GenResult, p: CityParams):
    """Строит ров, склоны и мосты для столицы."""
    size = result.size
    surface_grid = result.layers["surface"]
    nav_grid = result.layers["navigation"]

    # Сначала создаем ров и склоны
    _apply_moat_and_slopes(result, p)

    c = size // 2
    gate_start = c - p.gate_w // 2
    gate_end = gate_start + p.gate_w

    # Теперь создаем "мосты" через ров там, где должны быть ворота
    for i in range(gate_start, gate_end):
        # Северный мост
        for rz in range(p.r_slope1):
            surface_grid[rz][i] = KIND_ROAD
            nav_grid[rz][i] = NAV_BRIDGE
        # Южный мост
        for rz in range(size - p.r_slope1, size):
            surface_grid[rz][i] = KIND_ROAD
            nav_grid[rz][i] = NAV_BRIDGE
        # Западный мост
        for rx in range(p.r_slope1):
            surface_grid[i][rx] = KIND_ROAD
            nav_grid[i][rx] = NAV_BRIDGE
        # Восточный мост
        for rx in range(size - p.r_slope1, size):
            surface_grid[i][rx] = KIND_ROAD
            nav_grid[i][rx] = NAV_BRIDGE


def apply_starting_zone_rules(result: GenResult, preset: Any) -> None:
    """Главный диспетчер. Вызывает строитель для города."""
    params = CityParams.from_preset(preset)
    structure = get_structure_at(result.cx, result.cz)
    if not structure:
        return
    print(
        f"--- Applying rules for '{structure.name}' in chunk ({result.cx}, {result.cz}) ---"
    )
    if structure.name == "Столица":
        build_capital_city(result, params)
