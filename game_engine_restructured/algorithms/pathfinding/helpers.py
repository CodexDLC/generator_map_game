# game_engine/algorithms/pathfinding/helpers.py

from __future__ import annotations
from typing import Dict, Tuple, Optional, List
import math

from game_engine_restructured.core.constants import DEFAULT_TERRAIN_FACTOR
from game_engine_restructured.core.grid.hex import HexGridSpec

# --- ИЗМЕНЕНИЕ: Импортируем все из единого центра ---


# Координата клетки (q, r)
Coord = Tuple[int, int]

# Наборы соседей
NEI6_AXIAL: List[Coord] = [
    (1, 0), (1, -1), (0, -1),
    (-1, 0), (-1, 1), (0, 1)
]

# ------------------------- УТИЛИТЫ ЯЧЕЕК/СОСЕДЕЙ -------------------------


def in_bounds(w: int, h: int, x: int, z: int) -> bool:
    """Проверка, что (x,z) внутри [0..w-1]×[0..h-1]."""
    return 0 <= x < w and 0 <= z < h


def terrain_factor_of(
    kind: str, terrain_factor: Optional[Dict[str, float]] = None
) -> float:
    """Стоимость попадания в клетку данного типа."""
    tf = terrain_factor or DEFAULT_TERRAIN_FACTOR
    return tf.get(kind, 1.0)


def is_walkable(
    kind_grid: List[List[str]], x: int, z: int, terrain_factor: Optional[Dict[str, float]] = None
) -> bool:
    """Проходимость клетки определяется конечной стоимостью (< inf)."""
    k = kind_grid[z][x]
    return terrain_factor_of(k, terrain_factor) < math.inf


def base_step_cost(dx: int, dz: int) -> float:
    """Цена шага для гекса: всегда 1.0 (за один переход)."""
    return 1.0


def elevation_penalty(
    height_grid: Optional[List[List[float]]],
    x: int,
    z: int,
    nx: int,
    nz: int,
    penalty_per_meter: float,
) -> float:
    """Штраф за перепад высот между (x,z) и (nx,nz)."""
    if not height_grid or penalty_per_meter <= 0.0:
        return 0.0
    try:
        h1 = float(height_grid[z][x])
        h2 = float(height_grid[nz][nx])
    except (IndexError, TypeError):
        return 0.0
    dh = abs(h2 - h1)
    return penalty_per_meter * dh


# ------------------------------ ЭВРИСТИКИ ------------------------------


def heuristic_hex(a: Coord, b: Coord) -> float:
    """Эвристика для гексагонов (cube-distance)."""
    return float(HexGridSpec.cube_distance(a[0], a[1], b[0], b[1]))


# ------------------------------ ПУТИ ------------------------------


def reconstruct(came_from: Dict[Coord, Coord], current: Coord) -> list[Coord]:
    """Восстановление пути из карты предков."""
    path = [current]
    while current in came_from:
        current = came_from[current]
        path.append(current)
    path.reverse()
    return path


def _side_of_gate(p: Tuple[int, int], w: int, h: int) -> str:
    x, z = p
    if x == 1:
        return "W"
    if x == w - 2:
        return "E"
    if z == 1:
        return "N"
    if z == h - 2:
        return "S"
    return "X"