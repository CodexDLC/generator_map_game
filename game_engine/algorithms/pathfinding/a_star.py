from __future__ import annotations
from typing import List, Tuple, Dict, Optional
import heapq
import math

from .policies import PathPolicy, NAV_POLICY
from .helpers import (
    Coord,
    in_bounds,
    base_step_cost,
    elevation_penalty,
    no_corner_cut,
    reconstruct,
)


def find_path(
    surface_grid: List[List[str]],
    nav_grid: List[List[str]],  # <-- Добавляем nav_grid
    height_grid: Optional[List[List[float]]],
    start_pos: Tuple[int, int],
    end_pos: Tuple[int, int],
    policy: PathPolicy = NAV_POLICY,
    cost_grid: Optional[List[List[float]]] = None,
) -> List[Tuple[int, int]] | None:
    if not surface_grid or not surface_grid[0]:
        return None

    w, h = len(surface_grid[0]), len(surface_grid)
    sx, sz = start_pos
    gx, gz = end_pos

    if not (in_bounds(w, h, sx, sz) and in_bounds(w, h, gx, gz)):
        return None
    # Проверяем проходимость по обоим слоям
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

    while open_heap:
        _, _, current = heapq.heappop(open_heap)
        if current in closed:
            continue
        if current == goal:
            return reconstruct(came_from, current)

        closed.add(current)
        cx, cz = current

        for dx, dz in policy.neighbors:
            nx, nz = cx + dx, cz + dz
            if not in_bounds(w, h, nx, nz):
                continue

            # --- ГЛАВНОЕ ИЗМЕНЕНИЕ: Проверяем проходимость по обоим слоям ---
            nav_kind = nav_grid[nz][nx]
            if policy.nav_factor.get(nav_kind, 1.0) == math.inf:
                continue

            surface_kind = surface_grid[nz][nx]

            # Проверка на срез углов (использует surface_grid, т.к. смотрит на стоимость)
            if (dx != 0 and dz != 0) and not policy.corner_cut:
                # Эта функция внутри себя проверяет стоимость, а не только проходимость
                if not no_corner_cut(
                    surface_grid, cx, cz, nx, nz, policy.terrain_factor
                ):
                    continue

            base = base_step_cost(dx, dz)
            elev = elevation_penalty(
                height_grid, cx, cz, nx, nz, policy.slope_penalty_per_meter
            )
            # Стоимость берем из слоя поверхностей
            terr = policy.terrain_factor.get(surface_kind, 1.0)

            additional_cost = cost_grid[nz][nx] if cost_grid else 1.0
            step_cost = (base * terr + elev) * additional_cost

            tentative_g = g_score[current] + step_cost
            nbr: Coord = (nx, nz)

            if tentative_g < g_score.get(nbr, math.inf):
                came_from[nbr] = current
                g_score[nbr] = tentative_g
                tie_breaker += 1
                f_score = tentative_g + policy.heuristic(nbr, goal)
                heapq.heappush(open_heap, (f_score, tie_breaker, nbr))
    return None
