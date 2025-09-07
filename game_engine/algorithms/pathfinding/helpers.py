from __future__ import annotations
from typing import Dict, Tuple, Optional
import math

# --- ИЗМЕНЕНИЕ: Импортируем все из единого центра ---
from game_engine.core.constants import DEFAULT_TERRAIN_FACTOR

# Координата клетки (x, z)
Coord = Tuple[int, int]

# Наборы соседей
NEI4: Tuple[Coord, ...] = ((-1, 0), (1, 0), (0, -1), (0, 1))
NEI8: Tuple[Coord, ...] = NEI4 + ((-1, -1), (1, -1), (-1, 1), (1, 1))

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
    kind_grid, x: int, z: int, terrain_factor: Optional[Dict[str, float]] = None
) -> bool:
    """Проходимость клетки определяется конечной стоимостью (< inf)."""
    k = kind_grid[z][x]
    return terrain_factor_of(k, terrain_factor) < math.inf


def base_step_cost(dx: int, dz: int) -> float:
    """Цена шага: прямой = 1, диагональ = sqrt(2)."""
    return math.sqrt(2.0) if (dx != 0 and dz != 0) else 1.0


def elevation_penalty(
    height_grid: Optional[list[list[float]]],
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
    except Exception:
        return 0.0
    dh = abs(h2 - h1)
    return penalty_per_meter * dh


def no_corner_cut(
    kind_grid,
    x: int,
    z: int,
    nx: int,
    nz: int,
    terrain_factor: Optional[Dict[str, float]] = None,
) -> bool:
    """
    Запрет «резать углы»:
    диагональный ход допустим только если обе ортогональные клетки также проходимы.
    """
    dx = nx - x
    dz = nz - z
    if dx != 0 and dz != 0:  # диагональ
        a = (x + dx, z)
        b = (x, z + dz)
        w = len(kind_grid[0])
        h = len(kind_grid)
        if not (in_bounds(w, h, *a) and in_bounds(w, h, *b)):
            return False
        return is_walkable(kind_grid, *a, terrain_factor) and is_walkable(
            kind_grid, *b, terrain_factor
        )
    return True


# ------------------------------ ЭВРИСТИКИ ------------------------------


def heuristic_l1(a: Coord, b: Coord) -> float:
    """Манхэттен (для 4-соседей)."""
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def heuristic_octile(a: Coord, b: Coord) -> float:
    """Octile (для 8-соседей, допустимая и согласованная)."""
    dx = abs(a[0] - b[0])
    dz = abs(a[1] - b[1])
    D, D2 = 1.0, math.sqrt(2.0)
    return D * (dx + dz) + (D2 - 2.0 * D) * min(dx, dz)


# ------------------------------ ПУТИ ------------------------------


def reconstruct(came_from: Dict[Coord, Coord], current: Coord) -> list[Coord]:
    """Восстановление пути из карты предков."""
    path = [current]
    while current in came_from:
        current = came_from[current]
        path.append(current)
    path.reverse()
    return path


def _side_of_gate(p: tuple[int, int], w: int, h: int) -> str:
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
