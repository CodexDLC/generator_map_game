from __future__ import annotations

import random
from typing import List, Tuple, Optional

from .policies import PathPolicy, ROAD_POLICY

try:
    from engine.worldgen_core.base.constants import (
        KIND_GROUND, KIND_WATER, KIND_OBSTACLE, KIND_SLOPE, KIND_VOID, KIND_ROAD
    )
except Exception:
    KIND_GROUND, KIND_WATER, KIND_OBSTACLE, KIND_SLOPE, KIND_VOID, KIND_ROAD = \
        "ground", "water", "obstacle", "slope", "void", "road"


Coord = Tuple[int, int]


# ------------------------- политика для локальных дорог -------------------------

def make_local_road_policy(base: PathPolicy = ROAD_POLICY,
                           slope_cost: float = 1.5,
                           water_cost: float = 12.0) -> PathPolicy:
    """
    Разрешаем slope (дороже земли), воду — очень дорого. Штраф за уклон отключён.
    """
    tf = dict(base.terrain_factor)
    tf[KIND_SLOPE] = slope_cost
    tf[KIND_WATER] = water_cost
    return base.with_overrides(terrain_factor=tf, slope_penalty_per_meter=0.0)


# ------------------------- площадка/якорь «хаба» -------------------------

def hub_rect(size: int, preset) -> tuple[int, int, int, int]:
    """
    Прямоугольник площадки (x0,z0,x1,z1) из preset.hub_pad;
    если pad выключен — центральный блок 1/3 стороны.
    """
    cfg_hp = getattr(preset, "hub_pad", {}) or {}
    if cfg_hp.get("enabled", False):
        pad = max(1, int(cfg_hp.get("size_tiles", 3)))
        c = size // 2
        x0 = max(0, c - pad // 2); x1 = min(size, x0 + pad)
        z0 = max(0, c - pad // 2); z1 = min(size, z0 + pad)
        return x0, z0, x1, z1
    return size // 3, size // 3, (2 * size) // 3, (2 * size) // 3


def hub_anchor(kind: List[List[str]], preset) -> Coord:
    """
    Лучшая клетка внутри площадки: ground > slope > water; иначе центр прямоугольника.
    """
    h = len(kind); w = len(kind[0]) if h else 0
    x0, z0, x1, z1 = hub_rect(w, preset)
    cx = (x0 + x1) // 2; cz = (z0 + z1) // 2

    def rank(k: str) -> int:
        if k == KIND_GROUND: return 0
        if k == KIND_SLOPE:  return 1
        if k == KIND_WATER:  return 2
        return 9999

    best: Optional[Coord] = None
    best_score = 10**9
    for z in range(z0, z1):
        for x in range(x0, x1):
            k = kind[z][x]; r = rank(k)
            if r >= 9999: 
                continue
            d = abs(x - cx) + abs(z - cz)
            s = r * 10000 + d
            if s < best_score:
                best_score = s; best = (x, z)
    return best if best else (cx, cz)

def _scan_edge_from_center(side: str, w: int, h: int, inset: int = 1):
    """Итератор по клеткам на грани, начиная от центра к краям (внутренняя линия с отступом)."""
    xc, zc = w // 2, h // 2
    if side == "W":
        x = inset
        for d in range(0, max(zc - inset, h - 1 - inset) + 1):
            for z in (zc - d, zc + d):
                if inset <= z < h - inset:
                    yield (x, z)
    elif side == "E":
        x = w - 1 - inset
        for d in range(0, max(zc - inset, h - 1 - inset) + 1):
            for z in (zc - d, zc + d):
                if inset <= z < h - inset:
                    yield (x, z)
    elif side == "N":
        z = inset
        for d in range(0, max(xc - inset, w - 1 - inset) + 1):
            for x in (xc - d, xc + d):
                if inset <= x < w - inset:
                    yield (x, z)
    elif side == "S":
        z = h - 1 - inset
        for d in range(0, max(xc - inset, w - 1 - inset) + 1):
            for x in (xc - d, xc + d):
                if inset <= x < w - inset:
                    yield (x, z)


# ------------------------- выбор «гейта» на грани чанка -------------------------

def _passable_for_gate(kind: str) -> bool:
    # дорога — в приоритете, затем обычные проходимые типы
    return kind in (KIND_GROUND, KIND_SLOPE, KIND_WATER, KIND_ROAD)

def _edge_canonical_key(side: str, cx: int, cz: int) -> Tuple[str, int, int]:
    """
    Канонический ключ для общей грани.
    Горизонталь ('H'): северная грань чанка (cx,cz) и южная грань (cx,cz-1) → один ключ (cx, cz-1).
    Вертикаль   ('V'): восточная грань (cx,cz) и западная грань (cx-1,cz)     → один ключ (cx-1, cz).
    """
    if side == "N":   return ("H", cx, cz - 1)
    if side == "S":   return ("H", cx, cz)
    if side == "W":   return ("V", cx - 1, cz)
    if side == "E":   return ("V", cx, cz)
    return ("?", cx, cz)


def _rng_from_key(seed: int, orient: str, ex: int, ez: int) -> random.Random:
    """
    Детерминированный PRNG по мировому сиду и ключу ребра (без использования hash()).
    """
    v = (seed & 0x7fffffff)
    v ^= (ex * 1_000_003) & 0xffffffff
    v ^= (ez * 2_000_033) & 0xffffffff
    v ^= (0x9E3779B1 if orient == "H" else 0x85EBCA6B)
    return random.Random(v)

def find_edge_gate(kind_grid: List[List[str]], side: str,
                   seed: int, cx: int, cz: int, size: int) -> Optional[Coord]:
    """Выбрать точку «врезки» на грани чанка.
    1) Сперва ищем УЖЕ НАРИСОВАННУЮ ДОРОГУ на этой грани (стыковка со старт-гейтом).
    2) Если нет — берём первую проходимую клетку (ground/slope/water).
    """
    h = len(kind_grid)
    w = len(kind_grid[0]) if h else 0
    if not (w and h):
        return None

    # 1) приоритет: уже существующая дорога на грани
    for (x, z) in _scan_edge_from_center(side, w, h, inset=1):
        if kind_grid[z][x] == KIND_ROAD:
            return (x, z)

    # 2) fallback: любая проходимая клетка
    for (x, z) in _scan_edge_from_center(side, w, h, inset=1):
        if _passable_for_gate(kind_grid[z][x]):
            return (x, z)

    return None
