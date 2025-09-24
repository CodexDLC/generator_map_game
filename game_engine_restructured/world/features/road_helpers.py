# Файл: game_engine/world/features/road_helpers.py
from __future__ import annotations
from typing import List, Dict, Tuple
from collections import deque
import math

# --- НАЧАЛО ИЗМЕНЕНИЙ ---

from ...core.constants import NAV_WATER, NAV_OBSTACLE

# --- КОНЕЦ ИЗМЕНЕНИЙ ---


def carve_ramp_along_path(
    elev: list[list[float]],
    path: list[tuple[int, int]],
    *,
    max_slope: float = 0.5,
    width: int = 7,
) -> None:
    """
    Создает плавный пандус вдоль пути, гарантируя, что уклон никогда
    не превышает max_slope. (Версия 3.0 - Реализация по алгоритму пользователя)
    """
    if not path:
        return
    H, W = len(elev), len(elev[0]) if elev else 0
    if not (H and W):
        return

    # --- ЭТАП 1: Создаем идеализированный профиль высот пути ---

    path_heights: Dict[Tuple[int, int], float] = {
        pt: float(elev[pt[1]][pt[0]]) for pt in path
    }

    # Проход ВПЕРЕД: Срезаем слишком крутые подъемы
    for i in range(1, len(path)):
        p_prev, p_curr = path[i - 1], path[i]
        h_prev = path_heights[p_prev]
        h_curr = path_heights[p_curr]

        if h_curr > h_prev + max_slope:
            path_heights[p_curr] = h_prev + max_slope

    # Проход НАЗАД: Сглаживаем слишком крутые спуски, используя уже исправленные высоты
    for i in range(len(path) - 2, -1, -1):
        p_next, p_curr = path[i + 1], path[i]
        h_next = path_heights[p_next]
        h_curr = path_heights[p_curr]

        if h_curr > h_next + max_slope:
            path_heights[p_curr] = h_next + max_slope

    # --- ЭТАП 2: Применяем идеальный профиль к ландшафту с откосами ---
    modifications: Dict[Tuple[int, int], float] = {}
    radius = (width - 1) // 2
    road_radius = 1

    for (px, pz), road_h in path_heights.items():
        for dz_offset in range(-radius, radius + 1):
            for dx_offset in range(-radius, radius + 1):
                dist = math.sqrt(dx_offset * dx_offset + dz_offset * dz_offset)
                if dist > radius:
                    continue

                x, z = px + dx_offset, pz + dz_offset
                if not (0 <= x < W and 0 <= z < H):
                    continue

                original_h = elev[z][x]
                target_h: float

                if dist <= road_radius:
                    target_h = road_h
                else:
                    t = (dist - road_radius) / (radius - road_radius)
                    t = t * t * (3.0 - 2.0 * t)
                    target_h = road_h * (1 - t) + original_h * t

                modifications[(x, z)] = target_h

    for (x, z), final_h in modifications.items():
        elev[z][x] = final_h


def preprocess_water_bodies(nav_grid: List[List[str]], max_water_crossing_size: int):
    # Эта функция без изменений
    h = len(nav_grid)
    w = len(nav_grid[0]) if h else 0
    if not (w and h):
        return
    visited = [[False for _ in range(w)] for _ in range(h)]
    for z in range(h):
        for x in range(w):
            if nav_grid[z][x] == NAV_WATER and not visited[z][x]:
                water_body_tiles = []
                q = deque([(x, z)])
                visited[z][x] = True
                while q:
                    cx, cz = q.popleft()
                    water_body_tiles.append((cx, cz))
                    for dx, dz in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                        nx, nz = cx + dx, cz + dz
                        if (
                            0 <= nx < w
                            and 0 <= nz < h
                            and not visited[nz][nx]
                            and nav_grid[nz][nx] == NAV_WATER
                        ):
                            visited[nz][nx] = True
                            q.append((nx, nz))
                if len(water_body_tiles) > max_water_crossing_size:
                    for wx, wz in water_body_tiles:
                        nav_grid[wz][wx] = NAV_OBSTACLE
