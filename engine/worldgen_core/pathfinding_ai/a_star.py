# engine/worldgen_core/pathfinding_ai/a_star.py
from __future__ import annotations
from typing import List, Tuple, Dict, Optional
import heapq
import math

# Используем имена типов из движка (ground/obstacle/water/road/void)
try:
    from engine.worldgen_core.base.constants import (
        KIND_GROUND, KIND_OBSTACLE, KIND_WATER, KIND_ROAD, KIND_VOID
    )
except Exception:
    # fallback, если импорт недоступен
    KIND_GROUND = "ground"
    KIND_OBSTACLE = "obstacle"
    KIND_WATER = "water"
    KIND_ROAD = "road"
    KIND_VOID = "void"

Coord = Tuple[int, int]

# --- Стоимости ---
# Дорога чуть дешевле, чтобы поощрять движение по ней.
TERRAIN_FACTOR: Dict[str, float] = {
    KIND_GROUND:   1.0,
    KIND_ROAD:     0.6,
    KIND_OBSTACLE: math.inf,  # непроходимо
    KIND_WATER:    math.inf,  # непроходимо
    KIND_VOID:     math.inf,  # непроходимо
}

# Штраф за перепад высот (метры берём из height_grid).
SLOPE_PENALTY_PER_METER: float = 0.06

# 8 соседей (включая диагонали)
NEIGHBORS_8: Tuple[Coord, ...] = (
    (-1,  0), (1,  0), (0, -1), (0, 1),
    (-1, -1), (1, -1), (-1, 1), (1, 1),
)

def _in_bounds(w: int, h: int, x: int, z: int) -> bool:
    return 0 <= x < w and 0 <= z < h

def _is_walkable(kind_grid: List[List[str]], x: int, z: int) -> bool:
    k = kind_grid[z][x]
    return TERRAIN_FACTOR.get(k, 1.0) < math.inf

def _base_step_cost(dx: int, dz: int) -> float:
    # Прямой шаг = 1, диагональ = sqrt(2)
    return math.sqrt(2.0) if (dx != 0 and dz != 0) else 1.0

def _elevation_penalty(height_grid: Optional[List[List[float]]], x: int, z: int, nx: int, nz: int) -> float:
    if not height_grid:
        return 0.0
    try:
        h1 = float(height_grid[z][x])
        h2 = float(height_grid[nz][nx])
    except Exception:
        return 0.0
    dh = abs(h2 - h1)
    return SLOPE_PENALTY_PER_METER * dh

def _terrain_factor(kind_grid: List[List[str]], nx: int, nz: int) -> float:
    k = kind_grid[nz][nx]
    return TERRAIN_FACTOR.get(k, 1.0)

def _no_corner_cut(kind_grid: List[List[str]], x: int, z: int, nx: int, nz: int) -> bool:
    """
    Запрещаем «резать углы»: диагональный ход допустим, только если обе
    примыкающие ортогональные клетки тоже проходимы.
    """
    dx = nx - x
    dz = nz - z
    if dx != 0 and dz != 0:  # диагональ
        a = (x + dx, z)
        b = (x, z + dz)
        w = len(kind_grid[0]); h = len(kind_grid)
        if not (_in_bounds(w, h, *a) and _in_bounds(w, h, *b)):
            return False
        return _is_walkable(kind_grid, *a) and _is_walkable(kind_grid, *b)
    return True

def _heuristic(a: Coord, b: Coord) -> float:
    """
    Octile-эвристика для 8-связности (допустимая и согласованная).
    """
    dx = abs(a[0] - b[0])
    dz = abs(a[1] - b[1])
    D  = 1.0
    D2 = math.sqrt(2.0)
    return D * (dx + dz) + (D2 - 2 * D) * min(dx, dz)

def _reconstruct(came_from: Dict[Coord, Coord], current: Coord) -> List[Coord]:
    path = [current]
    while current in came_from:
        current = came_from[current]
        path.append(current)
    path.reverse()
    return path

def find_path(
    kind_grid: List[List[str]],
    height_grid: List[List[float]],
    start_pos: Tuple[int, int],
    end_pos: Tuple[int, int]
) -> List[Tuple[int, int]] | None:
    """
    Находит оптимальный путь для персонажа с помощью A*.
    Возвращает список координат от start_pos до end_pos или None, если путь не найден.

    Правила:
    - Проходимые: ground, road. Непроходимые: obstacle, water, void.
    - Цена шага = (1 или sqrt(2)) * terrain_factor(dst) + slope_penalty(|Δh|).
    - Без «срезания углов» по диагонали.
    - Эвристика — octile (без уклонов, чтобы оставаться допустимой).
    """
    if not kind_grid or not kind_grid[0]:
        return None
    w, h = len(kind_grid[0]), len(kind_grid)

    sx, sz = start_pos
    gx, gz = end_pos

    if not (_in_bounds(w, h, sx, sz) and _in_bounds(w, h, gx, gz)):
        return None
    if not _is_walkable(kind_grid, sx, sz):
        return None
    if not _is_walkable(kind_grid, gx, gz):
        return None

    start: Coord = (sx, sz)
    goal:  Coord = (gx, gz)

    open_heap: List[Tuple[float, int, Coord]] = []  # (f, tie, (x,z))
    heapq.heappush(open_heap, (0.0, 0, start))

    came_from: Dict[Coord, Coord] = {}
    g_score: Dict[Coord, float] = {start: 0.0}
    closed: set[Coord] = set()
    tie_breaker = 0

    while open_heap:
        f, _, current = heapq.heappop(open_heap)
        if current in closed:
            continue
        if current == goal:
            return _reconstruct(came_from, current)

        closed.add(current)
        cx, cz = current

        for dx, dz in NEIGHBORS_8:
            nx, nz = cx + dx, cz + dz
            if not _in_bounds(w, h, nx, nz):
                continue
            if not _is_walkable(kind_grid, nx, nz):
                continue
            if not _no_corner_cut(kind_grid, cx, cz, nx, nz):
                continue

            base = _base_step_cost(dx, dz)
            terr = _terrain_factor(kind_grid, nx, nz)
            elev = _elevation_penalty(height_grid, cx, cz, nx, nz)
            step_cost = base * terr + elev

            tentative_g = g_score[current] + step_cost
            nbr = (nx, nz)

            if tentative_g < g_score.get(nbr, math.inf):
                came_from[nbr] = current
                g_score[nbr] = tentative_g
                tie_breaker += 1
                f_score = tentative_g + _heuristic(nbr, goal)
                heapq.heappush(open_heap, (f_score, tie_breaker, nbr))

    return None
