# engine/worldgen_core/pathfinding_ai/local_roads.py
from __future__ import annotations
from typing import List, Optional, Dict
import random

from .routers import BaseRoadRouter
from .policies import ROAD_POLICY
from .road_helpers import (
    Coord, hub_anchor, find_edge_gate, make_local_road_policy,
)
from .network import apply_paths_to_grid
from .helpers import _side_of_gate  # определяет сторону по координате гейта


# ----------------------- выбор сторон-гейтов по правилам -----------------------

def _choose_gate_sides(seed: int, cx: int, cz: int) -> List[str]:
    """
    Правила:
      - стартовый (1,0) -> ['W','E','N']  # к воротам, на восток и на север
      - первые 5 чанков восточнее старта на оси z=0 (cx in [2..6], cz=0):
            запрещаем 'S'
      - прочие чанки: выбираем 2..4 стороны детерминированно от мирового сида
    """
    if cx == 1 and cz == 0:
        return ['W', 'E', 'N']

    allowed = ['N', 'E', 'S', 'W']
    if cz == 0 and 2 <= cx <= 6:
        # берег южнее — будущий океан: не даём южный порт
        allowed.remove('S')

    # детерминированный рандом на основе МИРОВОГО сида + координат
    r = random.Random((seed * 1_000_003) + (cx * 10_007) + (cz * 10_009) + 0xA5)
    k = r.randint(2, min(4, len(allowed)))
    r.shuffle(allowed)
    return allowed[:k]


def _prime_cross(kind, anchor: tuple[int, int], dirs: List[str], width: int = 2) -> None:
    """
    Короткий «крест» из центра в разрешённых направлениях.
    Нужен, чтобы первые шаги A* «прилипали» к центру.
    """
    x, z = anchor
    arms: List[List[Coord]] = []
    if 'E' in dirs: arms.append([(x, z), (x + 1, z)])
    if 'W' in dirs: arms.append([(x, z), (x - 1, z)])
    if 'S' in dirs: arms.append([(x, z), (x, z + 1)])
    if 'N' in dirs: arms.append([(x, z), (x, z - 1)])
    if arms:
        apply_paths_to_grid(
            kind, arms,
            width=max(1, int(width)),
            allow_slope=True,   # по склонам можно
            allow_water=False   # по воде — нет
        )


def _carve_ramp_along_path(
    elev: list[list[float]],
    path: list[tuple[int, int]],
    step_m: float = 1.0,
    width: int = 1
) -> None:
    """
    Делает ступенчатый профиль вдоль дороги и выравнивает поперечник на всю ширину.
    Для каждого шага пути ограничиваем |Δh| <= step_m и распространяем эту высоту
    на квадрат Чебышёва радиуса r = width-1 вокруг клетки пути.
    """
    if not path or step_m <= 0:
        return

    H = len(elev)
    W = len(elev[0]) if H else 0
    r = max(0, int(width) - 1)

    def clamp_set(nx: int, nz: int, val: float) -> None:
        if 0 <= nx < W and 0 <= nz < H:
            elev[nz][nx] = val

    # стартовая клетка и её поперечник
    x0, z0 = path[0]
    prev_h = float(elev[z0][x0])
    for dz in range(-r, r + 1):
        for dx in range(-r, r + 1):
            if max(abs(dx), abs(dz)) <= r:
                clamp_set(x0 + dx, z0 + dz, prev_h)

    # дальше идём по маршруту
    for (x, z) in path[1:]:
        h = float(elev[z][x])
        dh = h - prev_h
        if dh > step_m:
            h = prev_h + step_m
        elif dh < -step_m:
            h = prev_h - step_m

        # центр
        clamp_set(x, z, h)
        # поперечное выравнивание на всю ширину дороги
        for dz in range(-r, r + 1):
            for dx in range(-r, r + 1):
                if max(abs(dx), abs(dz)) <= r:
                    clamp_set(x + dx, z + dz, h)

        prev_h = h


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
      - якорь = лучшая клетка внутри площадки (hub_pad) или центрального блока 1/3;
      - стороны-гейты задаются правилами (_choose_gate_sides);
      - политика: ground < slope << water; obstacle/void — непроходимо; штраф за уклон выключен.
    """
    cx = int(params.get("cx", 0))
    cz = int(params.get("cz", 0))
    world_seed = int(params.get("seed", 0))

    # 1) якорь в хаб-площадке
    anchor = hub_anchor(kind, preset)

    # 2) какие стороны используем на этом чанке
    sides = _choose_gate_sides(world_seed, cx, cz)
    if not sides:
        return []

    # «праймим» коротким крестом в допустимых направлениях
    _prime_cross(kind, anchor, sides, width=max(1, int(width)))

    # 3) находим конкретные точки-гейты по выбранным сторонам
    gates: List[Coord] = []
    for s in sides:
        p = find_edge_gate(kind, s, world_seed, cx, cz, size)
        if p:
            gates.append(p)
    if not gates:
        return []

    # 4) роутер: slope разрешён (дороже), вода — очень дорого, без штрафа за Δh
    policy = make_local_road_policy(ROAD_POLICY, slope_cost=1.5, water_cost=12.0)
    router = BaseRoadRouter(policy=policy)

    # 5) тянем пути от якоря к каждому гейту — в порядке сторон
    w = h = size
    order = {s: i for i, s in enumerate(sides)}
    gates.sort(key=lambda p: (order.get(_side_of_gate(p, w, h), 999),
                              abs(p[0] - anchor[0]) + abs(p[1] - anchor[1])))

    paths: List[List[Coord]] = []
    roads_cfg = getattr(preset, "roads", {}) or {}
    ramp_step = float(roads_cfg.get("ramp_step_m", 1.0))

    for gate in gates:
        path = router.find(kind, height, anchor, gate)
        if not path:
            continue

        # 1) сразу рисуем, чтобы следующий путь «прилипал»
        apply_paths_to_grid(
            kind, [path],
            width=max(1, int(width)),
            allow_slope=True,   # по склонам можно
            allow_water=False   # по воде — нет (если нужны мосты, включим)
        )

        # 2) вырезаем «лестницу» по высоте вдоль дороги
        if height:
            _carve_ramp_along_path(
                height, path,
                step_m=float(getattr(getattr(preset, "roads", {}), "ramp_step_m", 1.0)),
                width=max(1, int(width)),
            )

        paths.append(path)

    return paths
