# Файл: game_engine_restructured/world/planners/river_planner.py
from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Dict, Tuple
import numpy as np
import random

from ...core.preset import Preset
from ...core.types import GenResult
from ..road_types import (
    GlobalCoord,
    RoadWaypoint,
)  # <--- Будем использовать Waypoint и для рек
from ..grid_utils import region_base


@dataclass
class RiverPlan:
    """План рек для одного региона. Содержит УПРОЩЕННЫЕ пути и 'гейты'."""

    # Словарь, где ключ - ID реки, а значение - список ее ключевых точек (waypoints)
    waypoints: Dict[int, List[RoadWaypoint]] = field(default_factory=dict)
    # Информация о точках выхода рек из региона
    gates: Dict[str, List[Dict]] = field(default_factory=dict)


# --- НАЧАЛО НОВОГО КОДА ---
def _simplify_path(
    path: List[GlobalCoord], chunk_size: int, step: int = 30
) -> List[RoadWaypoint]:
    """
    Упрощает детальный путь, оставляя только ключевые точки ("маяки").
    """
    if not path:
        return []

    simplified_waypoints = []
    last_chunk_key = None

    for i, (x, z) in enumerate(path):
        # Определяем, в каком чанке находится точка
        cx = x // chunk_size
        cz = z // chunk_size
        current_chunk_key = (cx, cz)

        is_gate = last_chunk_key is not None and current_chunk_key != last_chunk_key

        # Точку сохраняем, если это:
        # 1. Первая точка (исток)
        # 2. Последняя точка (устье)
        # 3. "Гейт" (переход между чанками)
        # 4. Каждая N-ная точка ("маяк")
        if i == 0 or i == len(path) - 1 or is_gate or (i % step == 0):
            # Если предыдущая точка стала гейтом из-за нас, помечаем ее
            if simplified_waypoints and is_gate:
                simplified_waypoints[-1].is_gate = True

            simplified_waypoints.append(RoadWaypoint(pos=(x, z), is_gate=is_gate))

        last_chunk_key = current_chunk_key

    return simplified_waypoints


# --- КОНЕЦ НОВОГО КОДА ---


def plan_rivers_for_region(
    stitched_heights: np.ndarray,
    stitched_nav: np.ndarray,
    preset: Preset,
    seed: int,
) -> RiverPlan:
    # ... (начало функции и создание flow_map без изменений)
    print("  -> Planning river networks...")
    water_cfg = preset.water
    if not water_cfg or not water_cfg.get("enabled"):
        return RiverPlan()

    rng = random.Random(seed)
    H, W = stitched_heights.shape
    sea_level = preset.elevation.get("sea_level_m", 15.0)

    flow_map = np.zeros_like(stitched_heights, dtype=np.int32)
    num_droplets = water_cfg.get("river_num_droplets", 4000)
    min_height_for_spring = sea_level + 20

    for _ in range(num_droplets):
        sz, sx = rng.randint(5, H - 6), rng.randint(5, W - 6)
        if stitched_heights[sz, sx] < min_height_for_spring:
            continue

        path = _trace_flow(sz, sx, stitched_heights, stitched_nav)
        if path:
            for x, z in path:
                flow_map[z, x] += 1

    river_plan = RiverPlan()
    river_id_counter = 0

    threshold = water_cfg.get("river_threshold", 0.01) * num_droplets

    river_z, river_x = np.where(flow_map > threshold)
    visited = np.zeros_like(flow_map, dtype=bool)

    for z, x in zip(river_z, river_x):
        if visited[z, x]:
            continue

        # --- НАЧАЛО ИЗМЕНЕНИЙ: Упрощаем путь перед сохранением ---
        full_path = _trace_flow(z, x, stitched_heights, stitched_nav)

        if full_path and len(full_path) > 50:
            # Упрощаем путь до "маяков"
            simplified_wps = _simplify_path(full_path, preset.size)
            river_plan.waypoints[river_id_counter] = simplified_wps
            river_id_counter += 1

            # Помечаем весь путь как посещенный
            for px, pz in full_path:
                visited[pz, px] = True
        # --- КОНЕЦ ИЗМЕНЕНИЙ ---

    print(f"    -> Planned {len(river_plan.waypoints)} rivers.")
    return river_plan


# ... (функция _trace_flow без изменений)
def _trace_flow(start_z, start_x, heights, nav):
    from ...core import constants as const

    path = []
    z, x = start_z, start_x
    H, W = heights.shape

    for _ in range(W * 2):
        path.append((x, z))

        if nav[z, x] == const.NAV_WATER:
            return path

        min_h = heights[z, x]
        best_next = None

        for dz in range(-1, 2):
            for dx in range(-1, 2):
                if dz == 0 and dx == 0:
                    continue
                nz, nx = z + dz, x + dx
                if 0 <= nz < H and 0 <= nx < W:
                    if heights[nz, nx] < min_h:
                        min_h = heights[nz, nx]
                        best_next = (nz, nx)

        if best_next:
            z, x = best_next
        else:
            return None
    return path
