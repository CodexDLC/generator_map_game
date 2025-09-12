# game_engine/algorithms/pathfinding/helpers.py
from __future__ import annotations
from typing import Dict, Tuple, Optional, List
import math

from ...core.grid.hex import HexGridSpec

# --- ИЗМЕНЕНИЕ: Добавляем импорт констант ---
from ...core import constants as const

# --- ИЗМЕНЕНИЕ: Полностью новый словарь стоимостей под новые текстуры ---
DEFAULT_TERRAIN_FACTOR: Dict[str, float] = {
    # --- Базовые слои ---
    const.KIND_BASE_DIRT: 1.0,  # Обычная земля - эталон скорости
    const.KIND_BASE_GRASS: 1.0,  # По траве идти так же легко, как по земле
    const.KIND_BASE_SAND: 1.5,  # По песку идти сложнее
    const.KIND_BASE_ROCK: 5.0,  # Скалы почти непроходимы (высокая стоимость)
    const.KIND_BASE_ROAD: 0.6,  # Дорога - самый быстрый путь
    const.KIND_BASE_CRACKED: 1.2,  # Растрескавшаяся земля чуть медленнее обычной
    const.KIND_BASE_WATERBED: 2.0,  # По дну водоема идти тяжело
    # --- Детальные слои тоже могут влиять на скорость ---
    const.KIND_OVERLAY_SNOW: 1.8,  # Глубокий снег сильно замедляет
    const.KIND_OVERLAY_LEAFS_GREEN: 1.1,  # Листья немного замедляют
    const.KIND_OVERLAY_LEAFS_AUTUMN: 1.1,
    const.KIND_OVERLAY_DIRT_GRASS: 1.0,  # Смесь земли и травы не меняет скорость
    const.KIND_OVERLAY_DESERT_STONES: 1.4,  # Камни в пустыне замедляют
}

Coord = Tuple[int, int]
NEI6_AXIAL: List[Coord] = [(1, 0), (1, -1), (0, -1), (-1, 0), (-1, 1), (0, 1)]


# (Остальной код файла остается без изменений)
def in_bounds(w: int, h: int, x: int, z: int) -> bool:
    return 0 <= x < w and 0 <= z < h


def terrain_factor_of(
    kind: str, terrain_factor: Optional[Dict[str, float]] = None
) -> float:
    tf = terrain_factor or DEFAULT_TERRAIN_FACTOR
    return tf.get(kind, 1.0)


def is_walkable(
    kind_grid: List[List[str]],
    x: int,
    z: int,
    terrain_factor: Optional[Dict[str, float]] = None,
) -> bool:
    k = kind_grid[z][x]
    return terrain_factor_of(k, terrain_factor) < math.inf


def base_step_cost(dx: int, dz: int) -> float:
    return 1.0


def elevation_penalty(
    height_grid: Optional[List[List[float]]],
    x: int,
    z: int,
    nx: int,
    nz: int,
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
