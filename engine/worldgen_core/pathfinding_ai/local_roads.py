# engine/worldgen_core/pathfinding_ai/local_roads.py
from __future__ import annotations
from typing import List, Optional, Dict, Tuple
import random

from .routers import BaseRoadRouter
from .policies import ROAD_POLICY
from .road_helpers import (
    Coord, hub_anchor, find_edge_gate, make_local_road_policy,
)
from .network import apply_paths_to_grid

# константа типа клетки дороги (для выборочного «реза» высоты)
try:
    from engine.worldgen_core.base.constants import KIND_ROAD
except Exception:
    KIND_ROAD = "road"


# ----------------------- выбор сторон-гейтов по правилам -----------------------

def _choose_gate_sides(seed: int, cx: int, cz: int) -> List[str]:
    """
    Правила:
      - стартовый (1,0) -> ['W','E','N']  (к воротам, на восток, на север)
      - первые 5 чанков восточнее старта на оси z=0 (cx in [2..6], cz=0): без 'S'
      - прочие: 2..4 стороны детерминированно от мирового сида
    """
    if cx == 1 and cz == 0:
        return ['W', 'E', 'N']

    allowed = ['N', 'E', 'S', 'W']
    if cz == 0 and 2 <= cx <= 6:
        allowed.remove('S')

    r = random.Random((seed * 1_000_003) + (cx * 10_007) + (cz * 10_009) + 0xA5)
    k = r.randint(2, min(4, len(allowed)))
    r.shuffle(allowed)
    return allowed[:k]


def _prime_cross(kind, anchor: Tuple[int, int], dirs: List[str], width: int = 2) -> None:
    """
    Короткие «усики» из якоря в указанных направлениях, чтобы A* цеплялся за центр.
    НИКАКИХ других побочек: anchor и dirs передаём СЮДА, а не вычисляем внутри.
    """
    x, z = anchor
    arms: List[List[Coord]] = []
    if 'E' in dirs: arms.append([(x, z), (x + 1, z)])
    if 'W' in dirs: arms.append([(x, z), (x - 1, z)])
    if 'S' in dirs: arms.append([(x, z), (x, z + 1)])
    if 'N' in dirs: arms.append([(x, z), (x, z - 1)])
    if arms:
        apply_paths_to_grid(kind, arms, width=max(1, int(width)),
                            allow_slope=True, allow_water=False)


def _side_of_gate(p: Tuple[int, int], w: int, h: int) -> str:
    """Определяем грань по координате врезки (внутренняя клетка, с inset=1)."""
    x, z = p
    if z == 1:         return 'N'
    if z == h - 2:     return 'S'
    if x == 1:         return 'W'
    if x == w - 2:     return 'E'
    return '?'


def _carve_ramp_along_path(
    elev: list[list[float]],
    path: list[tuple[int, int]],
    *,
    step_m: float = 1.0,
    width: int = 1,
    kind: Optional[list[list[str]]] = None
) -> None:
    """
    Подрезаем только резкие перепады: если |Δh| > step_m,
    сдвигаем текущую клетку на ±step_m к исходному рельефу.
    Поперечник (ширина width) выставляем ТОЛЬКО в изменённых точках.
    Ровные участки не трогаем.
    """
    if not path or step_m <= 0:
        return

    H = len(elev)
    W = len(elev[0]) if H else 0
    r = max(0, int(width) - 1)
    eps = 1e-6

    def is_road(x: int, z: int) -> bool:
        if not (0 <= x < W and 0 <= z < H):
            return False
        if kind is None:
            return True
        return kind[z][x] == KIND_ROAD

    # опорная высота — как в рельефе в стартовой точке
    x0, z0 = path[0]
    prev_h = float(elev[z0][x0])

    # ВНИМАНИЕ: стартовый поперечник НЕ рисуем — чтобы не «гладить» всю дорогу
    for (x, z) in path[1:]:
        orig = float(elev[z][x])
        dh = orig - prev_h

        if abs(dh) <= step_m + eps:
            # участок и так достаточно «пологий» — ничего не меняем
            prev_h = orig
            continue

        # нужно подрезать скачок ровно на step_m в сторону исходной высоты
        target = prev_h + (step_m if dh > 0 else -step_m)

        # правим ТОЛЬКО саму дорогу и её поперечник в этой точке
        if is_road(x, z):
            elev[z][x] = target
        for dz in range(-r, r + 1):
            for dx in range(-r, r + 1):
                if max(abs(dx), abs(dz)) <= r and is_road(x + dx, z + dz):
                    elev[z + dz][x + dx] = target

        # новая опорная высота — уже «подрезанная»
        prev_h = target



# ------------------------------ основная функция ------------------------------

def build_local_roads(
    kind: List[List[str]],
    height: Optional[List[List[float]]],
    size: int,
    preset,
    params: Dict,
    *,
    width: int = 1,
) -> List[List[Coord]]:
    """
    Прокладка дорог ВНУТРИ одного чанка:
      - anchor = лучшая клетка внутри площадки (hub_pad) или центрального блока 1/3;
      - стороны-гейты задаются правилами (_choose_gate_sides);
      - политика: ground < slope << water; obstacle/void — непроходимо;
                  штраф за уклон небольшой, чтобы не «залипать» на одной террасе.
    """
    cx = int(params.get("cx", 0))
    cz = int(params.get("cz", 0))
    world_seed = int(params.get("seed", 0))

    # 1) якорь и стороны
    anchor = hub_anchor(kind, preset)
    sides = _choose_gate_sides(world_seed, cx, cz)
    if not sides:
        return []

    # короткая «звёздочка» из центра сразу, чтобы следующие пути цеплялись
    _prime_cross(kind, anchor, sides, width=max(1, int(width)))

    # 2) гейты на выбранных сторонах
    gates: List[Coord] = []
    for s in sides:
        p = find_edge_gate(kind, s, world_seed, cx, cz, size)
        if p:
            gates.append(p)
    if not gates:
        return []

    # 3) роутер: slope разрешён (дороже), вода — очень дорого.
    policy = make_local_road_policy(ROAD_POLICY, slope_cost=1.5, water_cost=12.0)
    router = BaseRoadRouter(policy=policy)

    # порядок: сначала ближние к anchor, но внутри группы — согласно sides
    w = h = size
    order = {s: i for i, s in enumerate(sides)}
    def _l1(a: Tuple[int, int], b: Tuple[int, int]) -> int:
        return abs(a[0] - b[0]) + abs(a[1] - b[1])

    gates.sort(key=lambda p: (order.get(_side_of_gate(p, w, h), 999), _l1(p, anchor)))

    # 4) тянем пути
    paths: List[List[Coord]] = []
    # шаг лестницы: либо roads.ramp_step_m, либо берём из террасировки
    elev_cfg = getattr(preset, "elevation", {}) or {}
    default_step = float(elev_cfg.get("quantization_step_m", 1.0))
    ramp_step = float(getattr(getattr(preset, "roads", {}), "ramp_step_m", default_step))

    for gate in gates:
        path = router.find(kind, height, anchor, gate)
        if not path:
            continue

        # рисуем дорогу сразу, чтобы следующая «прилипала»
        apply_paths_to_grid(
            kind, [path],
            width=max(1, int(width)),
            allow_slope=True,   # по склонам можно
            allow_water=False   # мосты пока не строим
        )

        # вырезаем лестницу ТОЛЬКО под дорогой
        if height:
            _carve_ramp_along_path(
                height, path,
                step_m=ramp_step,
                width=max(1, int(width)),
                kind=kind,           # <<< ключевое — правим только клетки дороги
            )

        paths.append(path)

    return paths
