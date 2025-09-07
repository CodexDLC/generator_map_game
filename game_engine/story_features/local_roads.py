# Файл: game_engine/story_features/local_roads.py
from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from game_engine.core.preset import Preset

from ..core.types import GenResult
from ..world_structure.context import Region
from ..world_structure.regions import region_base

from ..algorithms.pathfinding.routers import BaseRoadRouter
from ..algorithms.pathfinding.network import apply_paths_to_grid, find_path_network
from ..algorithms.pathfinding.policies import make_road_policy
from .road_helpers import carve_ramp_along_path


def build_local_roads(result: GenResult, region: Region, preset: Preset) -> None:
    """
    Строит дороги внутри чанка, соединяя опорные точки из регионального плана.
    """
    chunk_key = (result.cx, result.cz)
    plan_for_chunk = (region.road_plan or {}).get(chunk_key)

    if not plan_for_chunk or not plan_for_chunk.waypoints:
        return

    region_size = preset.region_size
    base_cx, base_cz = region_base(region.scx, region.scz, region_size)
    chunk_size = result.size

    local_waypoints = []
    for wp in plan_for_chunk.waypoints:
        global_x, global_y = wp.pos
        local_x = global_x - ((result.cx - base_cx) * chunk_size)
        local_y = global_y - ((result.cz - base_cz) * chunk_size)
        if 0 <= local_x < chunk_size and 0 <= local_y < chunk_size:
            local_waypoints.append((local_x, local_y))

    if len(local_waypoints) < 2:
        return

    surface_grid = result.layers["surface"]
    nav_grid = result.layers["navigation"]
    overlay_grid = result.layers["overlay"]
    height_grid = result.layers["height_q"]["grid"]

    policy = make_road_policy(
        allow_slopes=True, allow_water_as_bridge=True, water_bridge_cost=15.0
    )
    router = BaseRoadRouter(policy=policy)

    paths = find_path_network(
        surface_grid, nav_grid, height_grid, local_waypoints, router=router
    )

    if not paths:
        print(f"[ROADS][WARN] chunk={chunk_key} Could not connect waypoints.")
        return

    for path in paths:
        if path:
            # --- ИЗМЕНЕНИЕ: Передаем новую ширину зоны выравнивания ---
            carve_ramp_along_path(
                height_grid, path, width=7
            )  # 3 (дорога) + 2*2 (откосы) = 7

    # --- ИЗМЕНЕНИЕ: Возвращаем визуальную ширину дороги к 3 ---
    apply_paths_to_grid(surface_grid, nav_grid, overlay_grid, paths, width=3)
    print(f"[ROADS] chunk={chunk_key} Successfully applied paths.")
