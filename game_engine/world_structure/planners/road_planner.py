# Замените ВСЁ содержимое файла на этот код:

from __future__ import annotations
from typing import Dict, List, Tuple
from collections import defaultdict

# --- Импорты ---
from ..grid_utils import REGION_SIZE, region_base
from ...core.types import GenResult
from ...story_features.story_definitions import get_structure_at
from ...algorithms.pathfinding.a_star import find_path as astar_find
from ...algorithms.pathfinding.policies import make_tract_policy, make_road_policy  # <-- Важный импорт
from ..road_types import GlobalCoord, RoadWaypoint, ChunkRoadPlan
from ...core.preset import Preset
from ...core.constants import KIND_GROUND, KIND_WATER, KIND_SLOPE


# --- Вспомогательные функции (без изменений) ---

def _stitch_region_maps(base_chunks: Dict[Tuple[int, int], GenResult], scx: int, scz: int, preset: Preset) -> List[
    List[str]]:
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


# --- НОВАЯ ФУНКЦИЯ ДЛЯ КАРТЫ ШТРАФОВ ---
def _create_water_cost_grid(original_map: List[List[str]], penalty: float = 50.0) -> List[List[float]]:
    """Создает карту штрафов, делая клетки рядом с водой "дорогими"."""
    height = len(original_map)
    if height == 0: return []
    width = len(original_map[0])

    cost_grid = [[1.0 for _ in range(width)] for _ in range(height)]

    for z in range(height):
        for x in range(width):
            if original_map[z][x] == KIND_WATER:
                continue
            is_near_water = False
            for dz in range(-1, 2):
                for dx in range(-1, 2):
                    if dx == 0 and dz == 0: continue
                    nx, nz = x + dx, z + dz
                    if 0 <= nx < width and 0 <= nz < height and original_map[nz][nx] == KIND_WATER:
                        is_near_water = True
                        break
                if is_near_water: break
            if is_near_water:
                cost_grid[z][x] = penalty
    return cost_grid

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


# --- НОВАЯ, ПРАВИЛЬНАЯ ВЕРСИЯ ГЛАВНОЙ ФУНКЦИИ ---

def plan_roads_for_region(scx: int, scz: int, seed: int, preset: Preset, base_chunks: Dict[Tuple[int, int], GenResult],
                          biome_type: str) -> Dict[Tuple[int, int], ChunkRoadPlan]:
    base_cx, base_cz = region_base(scx, scz)
    chunk_size = preset.size
    region_pixel_size = REGION_SIZE * chunk_size

    print(f"[RoadPlanner] Region ({scx},{scz}) starting...")
    stitched_map = _stitch_region_maps(base_chunks, scx, scz, preset)
    all_global_paths: List[List[GlobalCoord]] = []

    if scx == 0 and scz == 0:
        print("[RoadPlanner] -> Starting region. Planning 4 main TRACTS.")
        print("[RoadPlanner] -> Creating water cost grid...")
        water_cost_grid = _create_water_cost_grid(stitched_map)  # Создаем карту штрафов

        capital_struct = get_structure_at(0, 0)
        if not capital_struct: return {}

        center_chunk_dx = capital_struct.cx - base_cx
        center_chunk_dz = capital_struct.cz - base_cz
        start_pos = (center_chunk_dx * chunk_size + chunk_size // 2, center_chunk_dz * chunk_size + chunk_size // 2)

        margin = 5
        center_coord = region_pixel_size // 2
        end_points = {"N": (center_coord, margin), "S": (center_coord, region_pixel_size - 1 - margin),
                      "W": (margin, center_coord), "E": (region_pixel_size - 1 - margin, center_coord)}

        tract_policy = make_tract_policy()
        for direction, end_pos in end_points.items():
            print(f"[RoadPlanner] -> Planning TRACT towards {direction}...")
            # Передаем карту штрафов в A*
            path = astar_find(stitched_map, None, start_pos, end_pos, policy=tract_policy, cost_grid=water_cost_grid)
            if path:
                all_global_paths.append(path)
    else:
        print("[RoadPlanner] -> Non-starting region. Planning trails between POIs.")

        # 1. Находим все "входы" в регион (пока заглушка, но это наш план)
        entry_gates = []  # TODO: Реализовать поиск гейтов от соседей

        # 2. Вызываем наш новый POI планировщик
        # biome_type нужно будет получить из RegionManager/WorldActor
        biome_type = "placeholder_biome"  # Пока используем заглушку
        procedural_pois = plan_pois_for_region(stitched_map, biome_type)

        # 3. Собираем все точки, которые нужно соединить
        all_points = entry_gates + procedural_pois
        if len(all_points) < 2:
            print("[RoadPlanner] -> Not enough points to connect. Skipping trail planning.")
            return {}

        # 4. Строим "скелет" (MST) и пути (A*) для тропинок
        poi_coords = [p.pos for p in all_points]
        mst_edges = _build_global_mst(poi_coords)

        # Для тропинок используем обычную политику, а не для трактов
        trail_policy = make_road_policy(pass_water=True, water_cost=15.0)
        for i, j in mst_edges:
            path = astar_find(stitched_map, None, poi_coords[i], poi_coords[j], policy=trail_policy)
            if path:
                all_global_paths.append(path)

    # "Нарезка" путей (без изменений)
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