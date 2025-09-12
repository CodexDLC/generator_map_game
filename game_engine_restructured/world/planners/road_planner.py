# Файл: game_engine/world/planners/road_planner.py
from __future__ import annotations
from typing import Dict, List, Tuple
from collections import defaultdict

from ...core import constants as const
from ..grid_utils import region_base
from ...core.types import GenResult
from ..road_types import GlobalCoord, RoadWaypoint, ChunkRoadPlan
from ...core.preset import Preset


def plan_roads_for_region(
    scx: int,
    scz: int,
    seed: int,
    preset: Preset,
    base_chunks: Dict[Tuple[int, int], GenResult],
) -> Dict[Tuple[int, int], ChunkRoadPlan]:
    """
    Планирует только КЛЮЧЕВЫЕ точки для дорог (маяки),
    а не полный путь.
    """
    region_size = preset.region_size
    base_cx, base_cz = region_base(scx, scz, region_size)
    chunk_size = preset.size
    region_pixel_size = region_size * chunk_size

    print(f"[RoadPlanner] Planning road waypoints for region ({scx},{scz})...")

    final_plan: Dict[Tuple[int, int], ChunkRoadPlan] = defaultdict(ChunkRoadPlan)

    # Дороги строим только в центральном регионе для старта
    if scx == 0 and scz == 0:
        print("  -> Central region. Planning 4 main roads from center.")

        # 1. Центральная точка (перекресток)
        center_chunk_dx = 0 - base_cx
        center_chunk_dz = 0 - base_cz
        center_pos: GlobalCoord = (
            center_chunk_dx * chunk_size + chunk_size // 2,
            center_chunk_dz * chunk_size + chunk_size // 2,
        )
        center_waypoint = RoadWaypoint(pos=center_pos, is_structure=True)

        # Определяем, в какой чанк попадает центр
        center_cx_key = base_cx + (center_pos[0] // chunk_size)
        center_cz_key = base_cz + (center_pos[1] // chunk_size)
        final_plan[(center_cx_key, center_cz_key)].waypoints.append(center_waypoint)

        # 2. Четыре "гейта" на краях региона
        margin = 5  # Небольшой отступ от края

        # Северный гейт
        north_pos: GlobalCoord = (center_pos[0], margin)
        north_cx_key = base_cx + (north_pos[0] // chunk_size)
        north_cz_key = base_cz + (north_pos[1] // chunk_size)
        final_plan[(north_cx_key, north_cz_key)].waypoints.append(
            RoadWaypoint(pos=north_pos, is_gate=True)
        )

        # Южный гейт
        south_pos: GlobalCoord = (center_pos[0], region_pixel_size - 1 - margin)
        south_cx_key = base_cx + (south_pos[0] // chunk_size)
        south_cz_key = base_cz + (south_pos[1] // chunk_size)
        final_plan[(south_cx_key, south_cz_key)].waypoints.append(
            RoadWaypoint(pos=south_pos, is_gate=True)
        )

        # Западный гейт
        west_pos: GlobalCoord = (margin, center_pos[1])
        west_cx_key = base_cx + (west_pos[0] // chunk_size)
        west_cz_key = base_cz + (west_pos[1] // chunk_size)
        final_plan[(west_cx_key, west_cz_key)].waypoints.append(
            RoadWaypoint(pos=west_pos, is_gate=True)
        )

        # Восточный гейт
        east_pos: GlobalCoord = (region_pixel_size - 1 - margin, center_pos[1])
        east_cx_key = base_cx + (east_pos[0] // chunk_size)
        east_cz_key = base_cz + (east_pos[1] // chunk_size)
        final_plan[(east_cx_key, east_cz_key)].waypoints.append(
            RoadWaypoint(pos=east_pos, is_gate=True)
        )

    return dict(final_plan)
