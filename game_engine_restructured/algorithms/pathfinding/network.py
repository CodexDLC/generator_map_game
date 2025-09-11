# game_engine/algorithms/pathfinding/network.py
from __future__ import annotations
from typing import List, Tuple, Optional, Iterable
import math

# --- ИЗМЕНЕНИЯ: ---
from .routers import BaseRoadRouter
from .helpers import Coord
from ...core import constants as const


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
        surface_grid: list[list[str]],
        nav_grid: list[list[str]],
        overlay_grid: list[list[int]],
        paths: Iterable[list[tuple[int, int]]],
        width: int = 1,
        # --- ИЗМЕНЕНИЕ: Используем новую, правильную константу ---
        road_type: str = const.KIND_BASE_ROAD,
) -> None:
    h = len(surface_grid)
    w = len(surface_grid[0]) if h else 0

    # --- ИЗМЕНЕНИЕ: Получаем ID дороги по-новому ---
    road_id = const.SURFACE_KIND_TO_ID.get(road_type, 0)

    # --- Здесь была ошибка в типе surface_grid, исправлено ---
    def paint(x: int, z: int):
        if 0 <= x < w and 0 <= z < h:
            # --- ИЗМЕНЕНИЕ: Дорога должна менять базовый слой, а не overlay ---
            surface_grid[z][x] = road_type

            # --- ИЗМЕНЕНИЕ: Используем новые константы ---
            if nav_grid[z][x] == const.NAV_WATER:
                nav_grid[z][x] = const.NAV_BRIDGE
            else:
                nav_grid[z][x] = const.NAV_PASSABLE