from __future__ import annotations
from typing import List, Tuple, Optional, Iterable, Dict
import math

from .routers import BaseRoadRouter
from .helpers import Coord, in_bounds
try:
    # типы — только чтобы не перетирать воду/горы при рисовании
    from engine.worldgen_core.base.constants import (
        KIND_GROUND, KIND_ROAD, KIND_WATER, KIND_OBSTACLE, KIND_SLOPE, KIND_VOID
    )
except Exception:
    KIND_GROUND = "ground"
    KIND_ROAD = "road"
    KIND_WATER = "water"
    KIND_OBSTACLE = "obstacle"
    KIND_SLOPE = "slope"
    KIND_VOID = "void"


# ---------------------- MST (минимальное остовное дерево) ----------------------

def _l1(a: Coord, b: Coord) -> int:
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def _build_mst(points: List[Coord]) -> List[Tuple[int, int]]:
    """
    Простой Prim по L1-метрике по индексам точек.
    Возвращает список рёбер как пар индексов (i, j).
    """
    n = len(points)
    if n <= 1:
        return []
    used = [False] * n
    used[0] = True
    edges: List[Tuple[int, int]] = []
    # текущие лучшие расстояния до дерева
    best = [(_l1(points[0], points[i]), 0) for i in range(n)]
    best[0] = (0, 0)

    for _ in range(n - 1):
        # выбираем неиспользованную вершину с минимальной стоимостью
        j = -1
        best_cost = math.inf
        for i in range(n):
            if not used[i] and best[i][0] < best_cost:
                best_cost = best[i][0]
                j = i
        if j == -1:
            break
        used[j] = True
        # добавляем ребро в остов
        edges.append((best[j][1], j))
        # релаксируем
        for i in range(n):
            if not used[i]:
                d = _l1(points[j], points[i])
                if d < best[i][0]:
                    best[i] = (d, j)
    return edges


# ---------------------- Построение сети маршрутов ----------------------

def find_path_network(
    kind_grid: List[List[str]],
    height_grid: Optional[List[List[float]]],
    points: List[Coord],
    router: Optional[BaseRoadRouter] = None,
) -> List[List[Coord]]:
    """
    Строит сеть путей между заданными точками:
      1) строим MST по L1
      2) на каждое ребро зовём роутер (A* с политикой дорог)
      3) собираем список путей (без None)
    """
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


def ensure_connectivity(
    kind_grid: List[List[str]],
    points: List[Coord],
    paths: List[List[Coord]],
) -> None:
    """
    Грубая аварийная связность: если две соседние точки MST не соединились,
    «пробиваем» прямой коридор ground между ними (без учёта высоты/воды).
    Это лучше, чем оставить разрыв в сети, и совпадает с твоей старой логикой.
    """
    n = len(points)
    if n <= 1:
        return
    w = len(kind_grid[0]); h = len(kind_grid)

    have_edge: Dict[Tuple[Coord, Coord], bool] = {}
    for p in paths:
        if not p:
            continue
        have_edge[(p[0], p[-1])] = True
        have_edge[(p[-1], p[0])] = True

    for i, j in _build_mst(points):
        a, b = points[i], points[j]
        if have_edge.get((a, b)):
            continue

        # брезенхемовский коридор по прямой
        x1, z1 = a; x2, z2 = b
        dx = abs(x2 - x1); sx = 1 if x1 < x2 else -1
        dz = abs(z2 - z1); sz = 1 if z1 < z2 else -1
        err = dx - dz

        corridor: List[Coord] = []
        x, z = x1, z1
        while True:
            if in_bounds(w, h, x, z):
                kind_grid[z][x] = KIND_GROUND
                corridor.append((x, z))
            if x == x2 and z == z2:
                break
            e2 = 2 * err
            if e2 > -dz:
                err -= dz
                x += sx
            if e2 < dx:
                err += dx
                z += sz

        if corridor:
            paths.append(corridor)


# ---------------------- Отрисовка «дороги» в слой kind ----------------------

def apply_paths_to_grid(
    kind_grid: List[List[str]],
    paths: Iterable[List[Coord]],
    width: int = 1,
    *,
    allow_slope: bool = False,
    allow_water: bool = False,
) -> None:
    """Красим клетки пути в KIND_ROAD. Флаги разрешают перетирать slope/воду."""
    if width < 1:
        width = 1

    h = len(kind_grid)
    w = len(kind_grid[0]) if h else 0

    def can_paint(k: str) -> bool:
        if k == KIND_VOID or k == KIND_OBSTACLE:
            return False
        if k == KIND_WATER and not allow_water:
            return False
        if k == KIND_SLOPE and not allow_slope:
            return False
        return True

    def paint(x: int, z: int):
        if 0 <= x < w and 0 <= z < h and can_paint(kind_grid[z][x]):
            kind_grid[z][x] = KIND_ROAD

    r = max(0, width - 1)  # Чебышёв-дилатация
    for path in paths:
        if not path:
            continue
        for (x, z) in path:
            for dz in range(-r, r + 1):
                for dx in range(-r, r + 1):
                    if max(abs(dx), abs(dz)) <= r:
                        paint(x + dx, z + dz)