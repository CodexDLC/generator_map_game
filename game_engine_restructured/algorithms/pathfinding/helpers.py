# game_engine/algorithms/pathfinding/helpers.py
from __future__ import annotations
from typing import Dict, Tuple, Optional, List
import math

from ...core.grid.hex import HexGridSpec
# --- ИЗМЕНЕНИЕ: Добавляем импорт констант ---
from ...core import constants as const

# --- ИЗМЕНЕНИЕ: Переносим словарь стоимостей СЮДА ---
DEFAULT_TERRAIN_FACTOR: Dict[str, float] = {
    const.KIND_BASE_DIRT: 1.0,
    const.KIND_BASE_ROCK: 5.0,
    const.KIND_BASE_SAND: 1.2,
    const.KIND_ROAD_PAVED: 0.6,
    # --- Добавляем стоимости для базовых текстур биомов ---
    const.KIND_FOREST_FLOOR: 1.2,
    const.KIND_PLAINS_GRASS: 1.0,
    const.KIND_SAVANNA_DRYGRASS: 1.1,
    const.KIND_JUNGLE_DARKFLOOR: 1.4,
    const.KIND_DESERT_GROUND: 1.2,
    const.KIND_TAIGA_MOSS: 1.1,
    const.KIND_TUNDRA_SNOWGROUND: 1.3,
}

Coord = Tuple[int, int]
NEI6_AXIAL: List[Coord] = [
    (1, 0), (1, -1), (0, -1),
    (-1, 0), (-1, 1), (0, 1)
]

# (Остальной код файла остается без изменений)
def in_bounds(w: int, h: int, x: int, z: int) -> bool:
    return 0 <= x < w and 0 <= z < h

def terrain_factor_of(
    kind: str, terrain_factor: Optional[Dict[str, float]] = None
) -> float:
    tf = terrain_factor or DEFAULT_TERRAIN_FACTOR
    return tf.get(kind, 1.0)

def is_walkable(
    kind_grid: List[List[str]], x: int, z: int, terrain_factor: Optional[Dict[str, float]] = None
) -> bool:
    k = kind_grid[z][x]
    return terrain_factor_of(k, terrain_factor) < math.inf

def base_step_cost(dx: int, dz: int) -> float:
    return 1.0

def elevation_penalty(
    height_grid: Optional[List[List[float]]],
    x: int, z: int, nx: int, nz: int,
    penalty_per_meter: float,
) -> float:
    if not height_grid or penalty_per_meter <= 0.0:
        return 0.0
    try:
        h1 = float(height_grid[z][x])
        h2 = float(height_grid[nz][nx])
    except (IndexError, TypeError):
        return 0.0
    dh = abs(h2 - h1)
    return penalty_per_meter * dh

def heuristic_hex(a: Coord, b: Coord) -> float:
    return float(HexGridSpec.cube_distance(a[0], a[1], b[0], b[1]))

def reconstruct(came_from: Dict[Coord, Coord], current: Coord) -> list[Coord]:
    path = [current]
    while current in came_from:
        current = came_from[current]
        path.append(current)
    path.reverse()
    return path