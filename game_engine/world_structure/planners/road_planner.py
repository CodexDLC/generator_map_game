from typing import Dict, List, Tuple
from ..regions import Region, REGION_SIZE, region_base
from ...story_features.story_definitions import get_structure_at

OPPOSITE: Dict[str, str] = {'N':'S','S':'N','W':'E','E':'W'}
DIR: Dict[str, Tuple[int,int]] = {'N':(0,-1),'S':(0,1),'W':(-1,0),'E':(1,0)}

def _dedup(seq: List[str]) -> List[str]:
    seen = set()
    out: List[str] = []
    for s in seq:
        if s not in seen:
            seen.add(s); out.append(s)
    return out

def plan_roads_for_region(region: Region, seed: int) -> Dict[Tuple[int,int], List[str]]:
    """
    Возвращает план дорог для всех 7×7 чанков региона.
    Правило: дороги тянем К воротам строений.
    1) Для каждого строения внутри региона: его выход side -> соседний чанк получает OPPOSITE[side].
    2) Границы: если у соседа ВНЕ региона есть строение с выходом на нас, текущий чанк получает side.
    """
    plan: Dict[Tuple[int,int], List[str]] = {}

    base_cx, base_cz = region_base(region.scx, region.scz)
    size = REGION_SIZE

    # Инициализация ключей
    for dz in range(size):
        for dx in range(size):
            cx = base_cx + dx
            cz = base_cz + dz
            plan[(cx, cz)] = []

    # (1) Строения ВНУТРИ региона → стороны соседям
    for dz in range(size):
        for dx in range(size):
            cx = base_cx + dx
            cz = base_cz + dz
            s = get_structure_at(cx, cz)
            if not s:
                continue
            for side in s.exits.keys():
                dx1, dz1 = DIR[side]
                ncx, ncz = cx + dx1, cz + dz1
                # если сосед в нашем регионе — добавим сторону
                if (base_cx <= ncx < base_cx + size) and (base_cz <= ncz < base_cz + size):
                    plan[(ncx, ncz)].append(OPPOSITE[side])

    # (2) Строения СНАРУЖИ региона → наши стороны на границе
    for dz in range(size):
        for dx in range(size):
            cx = base_cx + dx
            cz = base_cz + dz
            sides = plan[(cx, cz)]

            for side, (dx1, dz1) in DIR.items():
                ncx, ncz = cx + dx1, cz + dz1
                # если сосед ВНЕ нашего региона — проверим строение у соседа
                if not (base_cx <= ncx < base_cx + size and base_cz <= ncz < base_cz + size):
                    ns = get_structure_at(ncx, ncz)
                    if ns and OPPOSITE[side] in ns.exits:
                        sides.append(side)

    # дедупликация
    for k in list(plan.keys()):
        plan[k] = _dedup(plan[k])

    # отладка
    print(f"[RoadPlanner] Region ({region.scx},{region.scz}) plan ready")
    return plan
