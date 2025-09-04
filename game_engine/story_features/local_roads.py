from __future__ import annotations
from typing import Any

from ..core.types import GenResult
from ..world_structure.context import Region
from ..world_structure.regions import region_base

from ..algorithms.pathfinding.routers import BaseRoadRouter
from ..algorithms.pathfinding.network import apply_paths_to_grid, find_path_network
from ..algorithms.pathfinding.policies import make_road_policy
from .road_helpers import carve_ramp_along_path


def build_local_roads(result: GenResult, region: Region) -> None:
    """
    Строит дороги внутри чанка, соединяя опорные точки из регионального плана.
    """
    chunk_key = (result.cx, result.cz)
    # Используем 'region' для получения плана, а не 'params'
    plan_for_chunk = (region.road_plan or {}).get(chunk_key)

    if not plan_for_chunk or not plan_for_chunk.waypoints:
        return

    print(f"[ROADS] chunk={chunk_key} Building road from {len(plan_for_chunk.waypoints)} waypoints.")

    # Переводим глобальные координаты в локальные
    base_cx, base_cz = region_base(region.scx, region.scz)
    chunk_size = result.size

    local_waypoints = []
    for wp in plan_for_chunk.waypoints:
        global_x, global_y = wp.pos
        local_x = global_x - ((result.cx - base_cx) * chunk_size)
        local_y = global_y - ((result.cz - base_cz) * chunk_size)
        # Убедимся, что точка находится внутри чанка, чтобы избежать ошибок
        if 0 <= local_x < chunk_size and 0 <= local_y < chunk_size:
            local_waypoints.append((local_x, local_y))

    if len(local_waypoints) < 2:
        return

    kind_grid = result.layers["kind"]
    height_grid = result.layers["height_q"]["grid"]

    policy = make_road_policy(allow_slopes=True, pass_water=True, water_cost=15.0, slope_penalty=0.05)
    router = BaseRoadRouter(policy=policy)

    paths = find_path_network(kind_grid, height_grid, local_waypoints, router=router)

    if not paths:
        print(f"[ROADS][WARN] chunk={chunk_key} Could not connect waypoints.")
        return

    for path in paths:
        if path:
            carve_ramp_along_path(height_grid, path)

    # --- ИЗМЕНЕНИЕ: Делаем дорогу шириной в 3 клетки ---
    apply_paths_to_grid(kind_grid, paths, width=3, allow_slope=True, allow_water=True)
    print(f"[ROADS] chunk={chunk_key} Successfully applied paths.")