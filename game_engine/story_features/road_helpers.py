# game_engine/story_features/road_helpers.py
from __future__ import annotations
from typing import List, Tuple, Optional, Iterator

# --- Импорты ---
from game_engine.algorithms.pathfinding.policies import PathPolicy, ROAD_POLICY
from game_engine.core.constants import (
    KIND_GROUND, KIND_WATER, KIND_SLOPE, KIND_ROAD, KIND_SAND
)
# --- Импортируем реестр для поиска точных координат ворот ---
from .story_definitions import get_structure_at
from ..world_structure.planners.road_planner import OPPOSITE_SIDE

Coord = Tuple[int, int]


# ------------------------- политика для локальных дорог -------------------------
def make_local_road_policy(base: PathPolicy = ROAD_POLICY,
                           slope_cost: float = 5.0,
                           water_cost: float = 15.0) -> PathPolicy:
    tf = dict(base.terrain_factor)
    tf[KIND_SLOPE] = slope_cost
    tf[KIND_WATER] = water_cost
    return base.with_overrides(terrain_factor=tf, slope_penalty_per_meter=0.05)


# ------------------------- площадка/якорь «хаба» -------------------------
def hub_rect(size: int, preset) -> tuple[int, int, int, int]:
    cfg_hp = getattr(preset, "hub_pad", {}) or {}
    if cfg_hp.get("enabled", False):
        pad = max(1, int(cfg_hp.get("size_tiles", 3)))
        c = size // 2
        x0 = max(0, c - pad // 2)
        x1 = min(size, x0 + pad)
        z0 = max(0, c - pad // 2)
        z1 = min(size, z0 + pad)
        return x0, z0, x1, z1
    return size // 3, size // 3, (2 * size) // 3, (2 * size) // 3


def hub_anchor(kind: List[List[str]], preset) -> Optional[Coord]:
    """
    Находит лучшую точку для центрального перекрестка, ИГНОРИРУЯ воду.
    Возвращает None, если в центре нет подходящей земли.
    """
    h = len(kind)
    w = len(kind[0]) if h else 0
    x0, z0, x1, z1 = hub_rect(w, preset)
    cx = (x0 + x1) // 2
    cz = (z0 + z1) // 2

    def rank(k: str) -> int:
        if k in (KIND_GROUND, KIND_SAND): return 0
        if k == KIND_SLOPE: return 1
        return 9999

    best: Optional[Coord] = None
    best_score = 10 ** 9
    for z in range(z0, z1):
        for x in range(x0, x1):
            k = kind[z][x]
            r = rank(k)
            if r >= 9999: continue
            d = abs(x - cx) + abs(z - cz)
            s = r * 10000 + d
            if s < best_score:
                best_score = s
                best = (x, z)
    return best


# ------------------------- итераторы по граням -------------------------
def _iter_from_center(center: int, max_val: int, inset: int) -> Iterator[int]:
    """Итерирует по координатам вдоль одной оси, начиная от центра."""
    max_dist = max(center - inset, max_val - 1 - inset - center)
    for d in range(max_dist + 1):
        p1 = center - d
        if inset <= p1 < max_val - inset: yield p1
        p2 = center + d
        if d != 0 and inset <= p2 < max_val - inset: yield p2


def _scan_edge_from_center(side: str, w: int, h: int, inset: int = 1):
    """Итератор по клеткам на грани, начиная от центра к краям."""
    xc, zc = w // 2, h // 2
    if side in ("N", "S"):
        z = inset if side == "N" else h - 1 - inset
        for x in _iter_from_center(xc, w, inset): yield x, z
    elif side in ("W", "E"):
        x = inset if side == "W" else w - 1 - inset
        for z in _iter_from_center(zc, h, inset): yield x, z


# ------------------------- выбор «гейта» на грани чанка -------------------------
def _passable_for_gate(kind: str) -> bool:
    """Определяет, можно ли в тайле такого типа разместить "ворота" для дороги."""
    return kind in (KIND_GROUND, KIND_SLOPE, KIND_ROAD, KIND_SAND)


def find_edge_gate(kind_grid: List[List[str]], side: str,
                   cx: int, cz: int, size: int) -> Optional[Coord]:
    """
    Выбрать точку «врезки» на грани чанка.
    Теперь она ищет гейт, если СОСЕДНИЙ чанк является особым строением.
    """
    h = len(kind_grid)
    w = len(kind_grid[0]) if h else 0
    if not (w and h): return None

    # 1. ПРОВЕРКА, НЕ ЯВЛЯЕТСЯ ЛИ СОСЕД ГОРОДОМ
    # Вычисляем координаты соседа в указанном направлении
    neighbor_cx, neighbor_cz = cx, cz
    if side == 'N':
        neighbor_cz -= 1
    elif side == 'S':
        neighbor_cz += 1
    elif side == 'W':
        neighbor_cx -= 1
    elif side == 'E':
        neighbor_cx += 1

    # Ищем строение в соседнем чанке
    structure = get_structure_at(neighbor_cx, neighbor_cz)

    # Если сосед - это строение, и у него есть выход в нашу сторону...
    opposite_side = OPPOSITE_SIDE[side]
    if structure and opposite_side in structure.exits:
        exit_def = structure.exits[opposite_side]
        # ...то мы вычисляем координаты гейта на НАШЕЙ стороне,
        # зеркально отражая позицию ворот города.
        pos = max(1, min(w - 2, int(size * exit_def.position_percent / 100)))

        if side == 'N': return (pos, 1)
        if side == 'S': return (pos, h - 2)
        if side == 'W': return (1, pos)
        if side == 'E': return (w - 2, pos)

    # 2. ЗАПАСНОЙ ВАРИАНТ (для обычных меж-чанковых дорог)
    for x, z in _scan_edge_from_center(side, w, h, inset=1):
        if kind_grid[z][x] == KIND_ROAD: return x, z
    for x, z in _scan_edge_from_center(side, w, h, inset=1):
        if _passable_for_gate(kind_grid[z][x]): return x, z

    return None