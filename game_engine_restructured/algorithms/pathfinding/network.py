# game_engine/algorithms/pathfinding/network.py
from __future__ import annotations
from typing import List, Tuple, Optional, Iterable
import math

import numpy as np

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
        surface_grid: np.ndarray,
        nav_grid: np.ndarray,
        overlay_grid: np.ndarray,
        paths: Iterable[list[tuple[int, int]]],
        width: int = 1,
) -> None:
    """
    Применяет пути к сеткам, работая с числовыми ID.
    """
    h, w = surface_grid.shape

    # --- НАЧАЛО ИЗМЕНЕНИЙ: Получаем ID напрямую из констант ---
    road_id = const.SURFACE_KIND_TO_ID[const.KIND_BASE_ROAD]
    water_id = const.NAV_KIND_TO_ID[const.NAV_WATER]
    bridge_id = const.NAV_KIND_TO_ID[const.NAV_BRIDGE]
    passable_id = const.NAV_KIND_TO_ID[const.NAV_PASSABLE]

    # --- КОНЕЦ ИЗМЕНЕНИЙ ---

    def paint(x: int, z: int):
        if 0 <= x < w and 0 <= z < h:
            # --- НАЧАЛО ИЗМЕНЕНИЙ: Работаем только с ID ---
            surface_grid[z, x] = road_id

            # Сравниваем и присваиваем ID, а не строки
            if nav_grid[z, x] == water_id:
                nav_grid[z, x] = bridge_id
            else:
                nav_grid[z, x] = passable_id
            # --- КОНЕЦ ИЗМЕНЕНИЙ ---

    # Расширяем линию до нужной ширины (этот код остается)
    # ... (код для отрисовки дороги остается без изменений,
    # он просто вызывает paint(x,z), который мы исправили)
    for path in paths:
        if not path:
            continue

        # Простой метод утолщения линии
        for px, pz in path:
            for dz_offset in range(-width, width + 1):
                for dx_offset in range(-width, width + 1):
                    if dx_offset * dx_offset + dz_offset * dz_offset <= width * width:
                        paint(px + dx_offset, pz + dz_offset)