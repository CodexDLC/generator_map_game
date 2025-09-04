# game_engine/story_features/road_helpers.py
from __future__ import annotations
from typing import List
from collections import deque

from game_engine.core.constants import (
    KIND_WATER, KIND_OBSTACLE
)


def carve_ramp_along_path(
        elev: list[list[float]],
        path: list[tuple[int, int]],
        *,
        ramp_step_m: float = 0.5,
        width: int = 3
) -> None:
    """
    Создает плавный пандус, "срезая" холмы, которые выше дороги.
    """
    if not path: return
    H, W = len(elev), len(elev[0]) if elev else 0
    if not (H and W): return

    path_heights = {pt: float(elev[pt[1]][pt[0]]) for pt in path}

    # сглаживание профиля туда-обратно
    for i in range(1, len(path)):
        p_prev, p_curr = path[i - 1], path[i]
        if abs(path_heights[p_curr] - path_heights[p_prev]) > ramp_step_m:
            path_heights[p_curr] = path_heights[p_prev] + ramp_step_m * (
                1 if path_heights[p_curr] > path_heights[p_prev] else -1)
    for i in range(len(path) - 2, -1, -1):
        p_next, p_curr = path[i + 1], path[i]
        if abs(path_heights[p_curr] - path_heights[p_next]) > ramp_step_m:
            path_heights[p_curr] = path_heights[p_next] + ramp_step_m * (
                1 if path_heights[p_curr] > path_heights[p_next] else -1)

    # ослабление к краям
    radius = (width - 1) // 2
    for (px, pz), target_h in path_heights.items():
        dist_to_border = min(px, pz, W - 1 - px, H - 1 - pz)
        strength = min(1.0, dist_to_border / 4.0)
        if strength <= 0: continue

        for dz in range(-radius, radius + 1):
            for dx in range(-radius, radius + 1):
                x, z = px + dx, pz + dz
                if 0 <= x < W and 0 <= z < H:
                    current_h = elev[z][x]
                    if current_h > target_h:
                        elev[z][x] = (current_h * (1 - strength)) + (target_h * strength)


def preprocess_water_bodies(grid: List[List[str]], max_water_crossing_size: int):
    """
    Большие водоемы (больше max_water_crossing_size) помечаем как OBSTACLE.
    """
    h = len(grid)
    w = len(grid[0]) if h else 0
    if not (w and h): return

    visited = [[False for _ in range(w)] for _ in range(h)]

    for z in range(h):
        for x in range(w):
            if grid[z][x] == KIND_WATER and not visited[z][x]:
                water_body_tiles = []
                q = deque([(x, z)])
                visited[z][x] = True

                while q:
                    cx, cz = q.popleft()
                    water_body_tiles.append((cx, cz))
                    for dx, dz in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                        nx, nz = cx + dx, cz + dz
                        if 0 <= nx < w and 0 <= nz < h and \
                                not visited[nz][nx] and grid[nz][nx] == KIND_WATER:
                            visited[nz][nx] = True
                            q.append((nx, nz))

                if len(water_body_tiles) > max_water_crossing_size:
                    for wx, wz in water_body_tiles:
                        grid[wz][wx] = KIND_OBSTACLE

