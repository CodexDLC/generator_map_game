# Файл: game_engine/world/planners/road_planner.py
from __future__ import annotations
from typing import Dict, List, Tuple
from collections import defaultdict

# --- ИЗМЕНЕНИЯ: ---
from ...core import constants as const
from ..grid_utils import region_base
from ...core.types import GenResult
from ...algorithms.pathfinding.a_star import find_path as astar_find
from ...algorithms.pathfinding.policies import make_road_policy
from ..road_types import GlobalCoord, RoadWaypoint, ChunkRoadPlan
from ...core.preset import Preset


def _stitch_region_maps(
    base_chunks: Dict[Tuple[int, int], GenResult], scx: int, scz: int, preset: Preset
) -> Dict[str, List[List[str]]]:
    """
    Склеивает слои 'surface' и 'navigation' со всех чанков региона в две большие карты.
    """
    chunk_size = preset.size
    region_size = preset.region_size
    region_pixel_size = region_size * chunk_size

    stitched_grids = {
        "surface": [
            [const.KIND_BASE_DIRT for _ in range(region_pixel_size)]
            for _ in range(region_pixel_size)
        ],
        "navigation": [
            [const.NAV_PASSABLE for _ in range(region_pixel_size)]
            for _ in range(region_pixel_size)
        ],
    }

    base_cx, base_cz = region_base(scx, scz, region_size)
    for (cx, cz), chunk_data in base_chunks.items():
        start_x = (cx - base_cx) * chunk_size
        start_y = (cz - base_cz) * chunk_size

        for layer_name in stitched_grids.keys():
            grid_to_paste = stitched_grids[layer_name]
            source_grid = chunk_data.layers.get(layer_name)
            if source_grid:
                for z in range(chunk_size):
                    for x in range(chunk_size):
                        grid_to_paste[start_y + z][start_x + x] = source_grid[z][x]

    return stitched_grids


def _create_water_cost_grid(
    nav_grid: List[List[str]], penalty: float = 50.0
) -> List[List[float]]:
    height = len(nav_grid)
    if height == 0:
        return []
    width = len(nav_grid[0])
    cost_grid = [[1.0 for _ in range(width)] for _ in range(height)]
    for z in range(height):
        for x in range(width):
            if nav_grid[z][x] == const.NAV_WATER:
                continue
            is_near_water = False
            for dz in range(-1, 2):
                for dx in range(-1, 2):
                    if dx == 0 and dz == 0:
                        continue
                    nx, nz = x + dx, z + dz
                    if (
                        0 <= nx < width
                        and 0 <= nz < height
                        and nav_grid[nz][nx] == const.NAV_WATER
                    ):
                        is_near_water = True
                        break
                if is_near_water:
                    break
            if is_near_water:
                cost_grid[z][x] = penalty
    return cost_grid


def _l1(p1: GlobalCoord, p2: GlobalCoord) -> int:
    return abs(p1[0] - p2[0]) + abs(p1[1] - p2[1])


def _build_global_mst(points: List[GlobalCoord]) -> List[Tuple[int, int]]:
    n = len(points)
    if n <= 1:
        return []
    used, edges, min_e, sel_e = [False] * n, [], [float("inf")] * n, [-1] * n
    min_e[0] = 0
    for _ in range(n):
        v = -1
        for i in range(n):
            if not used[i] and (v == -1 or min_e[i] < min_e[v]):
                v = i
        if v == -1:
            break
        used[v] = True
        if sel_e[v] != -1:
            edges.append((sel_e[v], v))
        for to in range(n):
            dist = _l1(points[v], points[to])
            if not used[to] and dist < min_e[to]:
                min_e[to], sel_e[to] = dist, v
    return edges


def plan_roads_for_region(
    scx: int,
    scz: int,
    seed: int,
    preset: Preset,
    base_chunks: Dict[Tuple[int, int], GenResult],
    biome_type: str,
) -> Dict[Tuple[int, int], ChunkRoadPlan]:
    region_size = preset.region_size
    base_cx, base_cz = region_base(scx, scz, region_size)
    chunk_size = preset.size
    region_pixel_size = region_size * chunk_size

    print(f"[RoadPlanner] Region ({scx},{scz}) starting...")

    stitched_grids = _stitch_region_maps(base_chunks, scx, scz, preset)
    stitched_surface_grid = stitched_grids["surface"]
    stitched_nav_grid = stitched_grids["navigation"]

    all_global_paths: List[List[GlobalCoord]] = []

    if scx == 0 and scz == 0:
        print("[RoadPlanner] -> Central region. Planning 4 main roads from crossroads.")
        water_cost_grid = _create_water_cost_grid(stitched_nav_grid)

        center_chunk_dx = 0 - base_cx
        center_chunk_dz = 0 - base_cz
        start_pos = (
            center_chunk_dx * chunk_size + chunk_size // 2,
            center_chunk_dz * chunk_size + chunk_size // 2,
        )

        margin = 5
        end_points = {
            "N": (start_pos[0], margin),
            "S": (start_pos[0], region_pixel_size - 1 - margin),
            "W": (margin, start_pos[1]),
            "E": (region_pixel_size - 1 - margin, start_pos[1]),
        }

        road_policy = make_road_policy()
        for direction, end_pos in end_points.items():
            print(f"[RoadPlanner] -> Planning road towards {direction}...")
            path = astar_find(
                stitched_surface_grid,
                stitched_nav_grid,
                None,
                start_pos,
                end_pos,
                policy=road_policy,
                cost_grid=water_cost_grid,
            )
            if path:
                all_global_paths.append(path)
    else:
        pass

    final_plan: Dict[Tuple[int, int], ChunkRoadPlan] = defaultdict(ChunkRoadPlan)
    for path in all_global_paths:
        last_chunk_key: Tuple[int, int] | None = None
        for i, (gx, gy) in enumerate(path):
            cx, cz = base_cx + (gx // chunk_size), base_cz + (gy // chunk_size)
            chunk_key = (cx, cz)
            is_gate = last_chunk_key is not None and last_chunk_key != chunk_key
            waypoint = RoadWaypoint(pos=(gx, gy), is_gate=is_gate)
            if is_gate and last_chunk_key is not None:
                final_plan[last_chunk_key].waypoints[-1].is_gate = True
            final_plan[chunk_key].waypoints.append(waypoint)
            last_chunk_key = chunk_key
    return dict(final_plan)