# game_engine/generators/world/road_helpers.py
from __future__ import annotations
from typing import List, Tuple, Optional, Iterator

# --- Импорты без изменений ---
from game_engine.algorithms.pathfinding.policies import PathPolicy, ROAD_POLICY
from game_engine.core.constants import (
    KIND_GROUND, KIND_WATER, KIND_SLOPE, KIND_ROAD
)

Coord = Tuple[int, int]


# ------------------------- политика для локальных дорог -------------------------
# (эта функция без изменений)
def make_local_road_policy(base: PathPolicy = ROAD_POLICY,
                           slope_cost: float = 1.5,
                           water_cost: float = 12.0) -> PathPolicy:
    tf = dict(base.terrain_factor)
    tf[KIND_SLOPE] = slope_cost
    tf[KIND_WATER] = water_cost
    return base.with_overrides(terrain_factor=tf, slope_penalty_per_meter=0.05)


# ------------------------- площадка/якорь «хаба» -------------------------
# (эти функции без изменений)
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


def hub_anchor(kind: List[List[str]], preset) -> Coord:
    h = len(kind)
    w = len(kind[0]) if h else 0
    x0, z0, x1, z1 = hub_rect(w, preset)
    cx = (x0 + x1) // 2
    cz = (z0 + z1) // 2

    def rank(k: str) -> int:
        if k == KIND_GROUND: return 0
        if k == KIND_SLOPE:  return 1
        if k == KIND_WATER:  return 2
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
    return best if best else (cx, cz)


# <<< НАЧАЛО ИЗМЕНЕНИЙ >>>

def _iter_from_center(center: int, max_val: int, inset: int) -> Iterator[int]:
    """
    Новая функция-помощник.
    Итерирует по координатам вдоль одной оси, начиная от центра и расходясь к краям.
    """
    # d - это расстояние от центра
    max_dist = max(center - inset, max_val - 1 - inset - center)
    for d in range(max_dist + 1):
        # Сначала точка "до" центра
        p1 = center - d
        if inset <= p1 < max_val - inset:
            yield p1
        # Затем точка "после" центра (если это не сам центр)
        p2 = center + d
        if d != 0 and inset <= p2 < max_val - inset:
            yield p2


def _scan_edge_from_center(side: str, w: int, h: int, inset: int = 1):
    """
    Переписанная функция без дублирования.
    Итератор по клеткам на грани, начиная от центра к краям.
    """
    xc, zc = w // 2, h // 2

    # Логика для Севера и Юга
    if side in ("N", "S"):
        z = inset if side == "N" else h - 1 - inset
        # Используем новую функцию-помощник для перебора X
        for x in _iter_from_center(xc, w, inset):
            yield x, z

    # Логика для Запада и Востока
    elif side in ("W", "E"):
        x = inset if side == "W" else w - 1 - inset
        # Используем новую функцию-помощник для перебора Z
        for z in _iter_from_center(zc, h, inset):
            yield x, z


# <<< КОНЕЦ ИЗМЕНЕНИЙ >>>

# ------------------------- выбор «гейта» на грани чанка -------------------------
# (остальные функции без изменений)
def _passable_for_gate(kind: str) -> bool:
    return kind in (KIND_GROUND, KIND_SLOPE, KIND_WATER, KIND_ROAD)


def find_edge_gate(kind_grid: List[List[str]], side: str,
                   cx: int, cz: int, size: int) -> Optional[Coord]: # <<< УБРАЛИ 'seed'
    """
    Выбрать точку «врезки» на грани чанка.
    """
    if cx == 1 and cz == 0 and side == 'W':
        return 1, size // 2

    h = len(kind_grid)
    w = len(kind_grid[0]) if h else 0
    if not (w and h):
        return None

    for x, z in _scan_edge_from_center(side, w, h, inset=1):
        if kind_grid[z][x] == KIND_ROAD:
            return x, z

    for x, z in _scan_edge_from_center(side, w, h, inset=1):
        if _passable_for_gate(kind_grid[z][x]):
            return x, z

    return None