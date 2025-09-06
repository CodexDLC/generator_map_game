# game_engine/algorithms/pathfinding/network.py
from __future__ import annotations
from typing import List, Tuple, Optional, Iterable
import math

# --- ИЗМЕНЕНИЯ: Правильные пути и константы ---
from .routers import BaseRoadRouter
from .helpers import Coord
from ...core.constants import (
    NAV_WATER, NAV_BRIDGE, KIND_ROAD, NAV_PASSABLE, SURFACE_KIND_TO_ID  # <-- Исправлено: KIND_ROAD вместо SURFACE_ROAD
)


def _l1(a: Coord, b: Coord) -> int:
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def _build_mst(points: List[Coord]) -> List[Tuple[int, int]]:
    # ... (код этой функции остается без изменений) ...
    n = len(points)
    if n <= 1: return []
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
        if j == -1: break
        used[j] = True
        edges.append((best[j][1], j))
        for i in range(n):
            if not used[i]:
                d = _l1(points[j], points[i])
                if d < best[i][0]: best[i] = (d, j)
    return edges


def find_path_network(
        surface_grid: List[List[str]],
        nav_grid: List[List[str]],
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
        path = r.find(surface_grid, nav_grid, height_grid, a, b)
        if path:
            paths.append(path)
    return paths


def apply_paths_to_grid(
        surface_grid: List[List[str]],
        nav_grid: List[List[str]],
        overlay_grid: List[List[int]],  # <-- Добавлен overlay_grid
        paths: Iterable[List[Coord]],
        width: int = 1,
) -> None:
    h = len(surface_grid)
    w = len(surface_grid[0]) if h else 0
    road_id = SURFACE_KIND_TO_ID[KIND_ROAD]  # Получаем ID дороги

    def paint(x: int, z: int):
        if 0 <= x < w and 0 <= z < h:
            # --- ИЗМЕНЕНИЕ: Рисуем ID дороги в оверлейный слой ---
            overlay_grid[z][x] = road_id

            # Обновляем навигацию, если под нами была вода
            if nav_grid[z][x] == NAV_WATER:
                nav_grid[z][x] = NAV_BRIDGE
            else:
                nav_grid[z][x] = NAV_PASSABLE

    for path in paths:
        if not path: continue
        for x, z in path:
            for dz in range(width):
                for dx in range(width):
                    paint(x + dx, z + dz)