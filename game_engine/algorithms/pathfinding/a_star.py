# game_engine/algorithms/pathfinding/a_star.py
from __future__ import annotations
from typing import List, Tuple, Dict, Optional
import heapq
import math

# --- НАЧАЛО ИЗМЕНЕНИЙ ---
# Импортируем новые константы и функции для гексагональной сетки
from .policies import PathPolicy, NAV_POLICY
from .helpers import (
    Coord,
    NEI6_AXIAL,
    base_step_cost,
    elevation_penalty,
    reconstruct,
    heuristic_hex,
)


# --- КОНЕЦ ИЗМЕНЕНИЙ ---


def find_path(
        surface_grid: List[List[str]],
        nav_grid: List[List[str]],  # <-- Добавляем nav_grid
        height_grid: Optional[List[List[float]]],
        start_pos: Tuple[int, int],
        end_pos: Tuple[int, int],
        policy: PathPolicy = NAV_POLICY,
        cost_grid: Optional[List[List[float]]] = None,
) -> List[Tuple[int, int]] | None:
    # --- НАЧАЛО ИЗМЕНЕНИЙ ---
    # Мы пока работаем с квадратной сеткой, но будем использовать гексагональную логику
    if not surface_grid or not surface_grid[0]:
        return None

    # Обратите внимание: координаты все еще (x,z) для совместимости с квадратным визуализатором
    w, h = len(surface_grid[0]), len(surface_grid)
    sx, sz = start_pos
    gx, gz = end_pos

    if not (0 <= sx < w and 0 <= sz < h and 0 <= gx < w and 0 <= gz < h):
        return None

    if policy.nav_factor.get(nav_grid[sz][sx], 1.0) == math.inf:
        return None
    if policy.nav_factor.get(nav_grid[gz][gx], 1.0) == math.inf:
        return None

    start: Coord = (sx, sz)
    goal: Coord = (gx, gz)
    open_heap: List[Tuple[float, int, Coord]] = []
    heapq.heappush(open_heap, (0.0, 0, start))
    came_from: Dict[Coord, Coord] = {}
    g_score: Dict[Coord, float] = {start: 0.0}
    closed: set[Coord] = set()
    tie_breaker = 0

    # --- УДАЛЕНО: Проверка in_bounds ---

    while open_heap:
        _, _, current = heapq.heappop(open_heap)
        if current in closed:
            continue
        if current == goal:
            return reconstruct(came_from, current)

        closed.add(current)
        cx, cz = current

        # Теперь перебираем соседей для гексагональной сетки, но в координатах odd-r
        # (это не настоящие гексы, а смещенные квадраты)
        for dx_hex, dz_hex in NEI6_AXIAL:
            # Преобразуем гекс-смещение в квадратное смещение (для odd-r)
            x_offset = dz_hex if cz % 2 == 1 else 0
            dx, dz = dx_hex + x_offset, dz_hex
            nx, nz = cx + dx, cz + dz

            if not (0 <= nx < w and 0 <= nz < h):
                continue

            nav_kind = nav_grid[nz][nx]
            if policy.nav_factor.get(nav_kind, 1.0) == math.inf:
                continue

            surface_kind = surface_grid[nz][nx]

            # Проверка на срез углов больше не нужна

            base = base_step_cost(dx, dz)
            elev = elevation_penalty(
                height_grid, cx, cz, nx, nz, policy.slope_penalty_per_meter
            )
            terr = policy.terrain_factor.get(surface_kind, 1.0)

            additional_cost = cost_grid[nz][nx] if cost_grid else 1.0
            step_cost = (base * terr + elev) * additional_cost

            tentative_g = g_score[current] + step_cost
            nbr: Coord = (nx, nz)

            if tentative_g < g_score.get(nbr, math.inf):
                came_from[nbr] = current
                g_score[nbr] = tentative_g
                tie_breaker += 1
                f_score = tentative_g + heuristic_hex(nbr, goal)
                heapq.heappush(open_heap, (f_score, tie_breaker, nbr))
    return None