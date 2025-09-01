from __future__ import annotations
from typing import List, Tuple, Dict, Optional
import heapq
import math

from .policies import PathPolicy, NAV_POLICY
from .helpers import (
    Coord, in_bounds, is_walkable, base_step_cost, elevation_penalty,
    no_corner_cut, reconstruct,
)

def find_path(
    kind_grid: List[List[str]],
    height_grid: Optional[List[List[float]]],
    start_pos: Tuple[int, int],
    end_pos: Tuple[int, int],
    policy: PathPolicy = NAV_POLICY,
) -> List[Tuple[int, int]] | None:
    """
    Универсальный A*: работает и для ИИ, и для прокладки дорог (через policy).
    Возвращает список координат (x,z) от start до goal или None.
    """
    if not kind_grid or not kind_grid[0]:
        return None

    w, h = len(kind_grid[0]), len(kind_grid)
    sx, sz = start_pos
    gx, gz = end_pos

    if not (in_bounds(w, h, sx, sz) and in_bounds(w, h, gx, gz)):
        return None
    if not is_walkable(kind_grid, sx, sz, policy.terrain_factor):
        return None
    if not is_walkable(kind_grid, gx, gz, policy.terrain_factor):
        return None

    start: Coord = (sx, sz)
    goal:  Coord = (gx, gz)

    open_heap: List[Tuple[float, int, Coord]] = []  # (f, tie, node)
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
            if not is_walkable(kind_grid, nx, nz, policy.terrain_factor):
                continue
            if (dx != 0 and dz != 0) and not policy.corner_cut:
                if not no_corner_cut(kind_grid, cx, cz, nx, nz, policy.terrain_factor):
                    continue

            base = base_step_cost(dx, dz)
            elev = elevation_penalty(height_grid, cx, cz, nx, nz, policy.slope_penalty_per_meter)
            terr = policy.terrain_factor.get(kind_grid[nz][nx], 1.0)
            step_cost = base * terr + elev

            tentative_g = g_score[current] + step_cost
            nbr: Coord = (nx, nz)

            if tentative_g < g_score.get(nbr, math.inf):
                came_from[nbr] = current
                g_score[nbr] = tentative_g
                tie_breaker += 1
                f_score = tentative_g + policy.heuristic(nbr, goal)
                heapq.heappush(open_heap, (f_score, tie_breaker, nbr))

    return None
