# game_engine/algorithms/pathfinding/network.py
from __future__ import annotations
from typing import List, Tuple, Optional, Iterable, Dict
import math

# --- ИЗМЕНЕНИЯ: Правильные пути ---
from .routers import BaseRoadRouter
from .helpers import Coord, in_bounds
from ...core.constants import (
    KIND_GROUND, KIND_ROAD, KIND_WATER, KIND_OBSTACLE, KIND_SLOPE, KIND_VOID, KIND_BRIDGE
)

def _l1(a: Coord, b: Coord) -> int:
    return abs(a[0] - b[0]) + abs(a[1] - b[1])

def _build_mst(points: List[Coord]) -> List[Tuple[int, int]]:
    n = len(points)
    if n <= 1:
        return []
    used = [False] * n
    used[0] = True
    edges: List[Tuple[int, int]] = []
    best = [(_l1(points[0], points[i]), 0) for i in range(n)]
    best[0] = (0, 0)

    for _ in range(n - 1):
        j = -1
        best_cost = math.inf
        for i in range(n):
            if not used[i] and best[i][0] < best_cost:
                best_cost = best[i][0]
                j = i
        if j == -1:
            break
        used[j] = True
        edges.append((best[j][1], j))
        for i in range(n):
            if not used[i]:
                d = _l1(points[j], points[i])
                if d < best[i][0]:
                    best[i] = (d, j)
    return edges

def find_path_network(
    kind_grid: List[List[str]],
    height_grid: Optional[List[List[float]]],
    points: List[Coord],
    router: Optional[BaseRoadRouter] = None,
) -> List[List[Coord]]:
    if not points:
        return []
    r = router or BaseRoadRouter()
    edges = _build_mst(points)
    paths: List[List[Coord]] = []
    for i, j in edges:
        a, b = points[i], points[j]
        path = r.find(kind_grid, height_grid, a, b)
        if path:
            paths.append(path)
    return paths

def apply_paths_to_grid(
    kind_grid: List[List[str]],
    paths: Iterable[List[Coord]],
    width: int = 1,
    *,
    allow_slope: bool = False,
    allow_water: bool = False,
) -> None:
    """
    Применяет пути к карте, создавая сплошную дорогу заданной ширины.
    (Финальная, упрощенная версия).
    """
    h = len(kind_grid)
    w = len(kind_grid[0]) if h else 0
    original_kind = [row[:] for row in kind_grid]

    def can_paint(k: str) -> bool:
        if k == KIND_VOID or k == KIND_OBSTACLE: return False
        if k == KIND_WATER and not allow_water: return False
        if k == KIND_SLOPE and not allow_slope: return False
        return True

    def paint(x: int, z: int):
        if 0 <= x < w and 0 <= z < h and can_paint(original_kind[z][x]):
            kind_grid[z][x] = KIND_BRIDGE if original_kind[z][x] == KIND_WATER else KIND_ROAD

    # --- НАЧАЛО ИЗМЕНЕНИЯ: Самая простая и правильная логика ---
    for path in paths:
        if not path:
            continue

        # Просто рисуем квадратный блок 'width' x 'width' в каждой точке пути.
        # Для width=2 это само по себе создает сплошную дорогу без разрывов.
        for x, z in path:
            for dz in range(width):
                for dx in range(width):
                    paint(x + dx, z + dz)