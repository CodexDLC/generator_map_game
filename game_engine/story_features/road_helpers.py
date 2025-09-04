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
    """Возвращает точку гейта на нашей границе; если у соседа-строения
    нет выхода на нас — возвращает None и запрещает fallback-сканирование."""

    OPPOSITE = {'N': 'S', 'S': 'N', 'W': 'E', 'E': 'W'}
    DIR = {'N': (0, -1), 'S': (0, 1), 'W': (-1, 0), 'E': (1, 0)}

    h = len(kind_grid)
    w = len(kind_grid[0]) if h else 0
    if not (w and h):
        return None

    # сосед по стороне
    dx, dz = DIR[side]
    n_cx, n_cz = cx + dx, cz + dz
    neighbor = get_structure_at(n_cx, n_cz)

    # если сосед — строение БЕЗ выхода на нас → гейта нет и fallback запрещён
    if neighbor and OPPOSITE[side] not in neighbor.exits:
        return None

    # если у соседа есть выход на нас → зеркалим его позицию
    if neighbor and OPPOSITE[side] in neighbor.exits:
        pos = int(size * neighbor.exits[OPPOSITE[side]].position_percent / 100)
        pos = max(1, min(w - 2, pos))
        if side == 'N': return (pos, 1)
        if side == 'S': return (pos, h - 2)
        if side == 'W': return (1,   pos)
        if side == 'E': return (w - 2, pos)

    # обычный случай: ищем готовую дорогу или проходимую клетку на нашей кромке
    for x, z in _scan_edge_from_center(side, w, h, inset=1):
        if kind_grid[z][x] == KIND_ROAD:
            return (x, z)
    for x, z in _scan_edge_from_center(side, w, h, inset=1):
        if _passable_for_gate(kind_grid[z][x]):
            return (x, z)

    return None


def _bridge_streak_over(kind: List[List[str]], path: List[Tuple[int,int]], limit: int) -> bool:
    cnt = 0
    for x, z in path:
        if kind[z][x] == KIND_WATER:
            cnt += 1
            if cnt > limit:
                return True
        else:
            cnt = 0
    return False