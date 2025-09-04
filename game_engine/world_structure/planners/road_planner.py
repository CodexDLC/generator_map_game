# game_engine/world_structure/planners/road_planner.py
from typing import Dict, List, Tuple, Optional
from collections import defaultdict

from ..regions import Region, REGION_SIZE, region_base
from ...core.types import GenResult
from ...story_features.story_definitions import get_structure_at
from ...algorithms.pathfinding.a_star import find_path as astar_find
from ...algorithms.pathfinding.policies import make_road_policy
from ..road_types import GlobalCoord, RoadWaypoint, ChunkRoadPlan
from ...core.preset import Preset
from ...core.constants import KIND_GROUND

def _stitch_region_maps(base_chunks: Dict[Tuple[int, int], GenResult], scx: int, scz: int, preset: Preset) -> List[List[str]]:
    """Сшивает 49 карт проходимости в одну большую."""
    chunk_size = preset.size
    region_pixel_size = REGION_SIZE * chunk_size
    grid = [[KIND_GROUND for _ in range(region_pixel_size)] for _ in range(region_pixel_size)]
    base_cx, base_cz = region_base(scx, scz)

    for (cx, cz), chunk_data in base_chunks.items():
        start_x = (cx - base_cx) * chunk_size
        start_y = (cz - base_cz) * chunk_size
        for z in range(chunk_size):
            for x in range(chunk_size):
                grid[start_y + z][start_x + x] = chunk_data.layers["kind"][z][x]
    return grid

def _l1(p1: GlobalCoord, p2: GlobalCoord) -> int:
    return abs(p1[0] - p2[0]) + abs(p1[1] - p2[1])


def _build_global_mst(points: List[GlobalCoord]) -> List[Tuple[int, int]]:
    n = len(points)
    if n <= 1: return []
    used, edges, min_e, sel_e = [False] * n, [], [float('inf')] * n, [-1] * n
    min_e[0] = 0
    for _ in range(n):
        v = -1
        for i in range(n):
            if not used[i] and (v == -1 or min_e[i] < min_e[v]):
                v = i
        if v == -1: break
        used[v] = True
        if sel_e[v] != -1: edges.append((sel_e[v], v))
        for to in range(n):
            dist = _l1(points[v], points[to])
            if not used[to] and dist < min_e[to]:
                min_e[to], sel_e[to] = dist, v
    return edges


def plan_roads_for_region(scx: int, scz: int, seed: int, preset: Preset, base_chunks: Dict[Tuple[int, int], GenResult]) -> Dict[Tuple[int, int], ChunkRoadPlan]:
    """Планировщик, работающий на реальной сшитой карте региона."""
    base_cx, base_cz = region_base(scx, scz)
    chunk_size = preset.size

    print(f"[RoadPlanner] Region ({scx},{scz}) starting...")
    # --- ИЗМЕНЕНИЕ: Используем реальную карту вместо "черновой" ---
    stitched_map = _stitch_region_maps(base_chunks, scx, scz, preset)

    points_of_interest: List[RoadWaypoint] = []
    for dz in range(REGION_SIZE):
        for dx in range(REGION_SIZE):
            cx, cz = base_cx + dx, base_cz + dz
            if get_structure_at(cx, cz):
                gx, gy = dx * chunk_size + chunk_size // 2, dz * chunk_size + chunk_size // 2
                points_of_interest.append(RoadWaypoint(pos=(gx, gy), is_structure=True))

    if len(points_of_interest) < 1: return {}  # Если нет даже одной точки, выходим

    poi_coords = [p.pos for p in points_of_interest]
    mst_edges = _build_global_mst(poi_coords)

    policy = make_road_policy(pass_water=True, water_cost=15.0)

    all_global_paths: List[List[GlobalCoord]] = []
    for i, j in mst_edges:
        path = astar_find(stitched_map, None, poi_coords[i], poi_coords[j], policy)
        if path: all_global_paths.append(path)

    final_plan: Dict[Tuple[int, int], ChunkRoadPlan] = defaultdict(ChunkRoadPlan)
    for path in all_global_paths:
        # --- НАЧАЛО ИЗМЕНЕНИЯ: Добавляем тип для ясности ---
        last_chunk_key: Tuple[int, int] | None = None
        # --- КОНЕЦ ИЗМЕНЕНИЯ ---
        for i, (gx, gy) in enumerate(path):
            cx, cz = base_cx + (gx // chunk_size), base_cz + (gy // chunk_size)
            chunk_key = (cx, cz)

            is_gate = last_chunk_key is not None and last_chunk_key != chunk_key
            waypoint = RoadWaypoint(pos=(gx, gy), is_gate=is_gate)

            # --- НАЧАЛО ИЗМЕНЕНИЯ: Добавляем явную проверку ---
            if is_gate and last_chunk_key is not None:
                final_plan[last_chunk_key].waypoints[-1].is_gate = True
            # --- КОНЕЦ ИЗМЕНЕНИЯ ---

            final_plan[chunk_key].waypoints.append(waypoint)
            last_chunk_key = chunk_key

    return dict(final_plan)