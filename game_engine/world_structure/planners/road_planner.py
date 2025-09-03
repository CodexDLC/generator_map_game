# game_engine/world_structure/planners/road_planner.py
from __future__ import annotations
from typing import Dict, Tuple, List
import random

from ...core.utils.rng import edge_key
from ...story_features.story_definitions import get_structure_at

# Словарь для получения противоположной стороны
OPPOSITE_SIDE = {'N': 'S', 'S': 'N', 'W': 'E', 'E': 'W'}


def plan_roads_for_region(
        scx: int, scz: int, world_seed: int, region_size: int
) -> Dict[Tuple[int, int], List[str]]:
    """
    Определяет, в каких чанках региона и по каким сторонам должны быть дороги.
    Теперь дороги ведут К городам, а не ИЗ них.
    """
    plan: Dict[Tuple[int, int], List[str]] = {}
    base_cx, base_cz = scx * region_size, scz * region_size

    # --- ЭТАП 1: ГЕНЕРАЦИЯ БАЗОВОЙ СЕТКИ ДОРОГ (без изменений) ---
    def get_border_rng(neighbor_scx, neighbor_scz):
        key_seed = edge_key(world_seed, scx, scz, neighbor_scx, neighbor_scz)
        return random.Random(key_seed)

    min_gates, max_gates = region_size // 2, region_size
    north_exits, south_exits, west_exits, east_exits = set(), set(), set(), set()

    # ... (весь код генерации случайных выходов и магистралей остается прежним)
    rng_n = get_border_rng(scx, scz - 1)
    k_n = rng_n.randint(min_gates, max_gates)
    north_exits.update(rng_n.sample(range(region_size), k_n))
    rng_s = get_border_rng(scx, scz + 1)
    k_s = rng_s.randint(min_gates, max_gates)
    south_exits.update(rng_s.sample(range(region_size), k_s))
    rng_w = get_border_rng(scx - 1, scz)
    k_w = rng_w.randint(min_gates, max_gates)
    west_exits.update(rng_w.sample(range(region_size), k_w))
    rng_e = get_border_rng(scx + 1, scz)
    k_e = rng_e.randint(min_gates, max_gates)
    east_exits.update(rng_e.sample(range(region_size), k_e))

    all_vertical_lanes = north_exits | south_exits
    for lx in all_vertical_lanes:
        for lz in range(region_size):
            cx, cz = base_cx + lx, base_cz + lz
            sides = plan.setdefault((cx, cz), [])
            if lz > 0: sides.append('N')
            if lz < region_size - 1: sides.append('S')
    all_horizontal_lanes = west_exits | east_exits
    for lz in all_horizontal_lanes:
        for lx in range(region_size):
            cx, cz = base_cx + lx, base_cz + lz
            sides = plan.setdefault((cx, cz), [])
            if lx > 0: sides.append('W')
            if lx < region_size - 1: sides.append('E')

    # --- ЭТАП 2: НАЛОЖЕНИЕ ПРАВИЛ ОТ ОСОБЫХ СТРОЕНИЙ ---
    for lz in range(region_size):
        for lx in range(region_size):
            cx, cz = base_cx + lx, base_cz + lz
            structure = get_structure_at(cx, cz)
            if structure:
                print(f"[RoadPlanner] Found '{structure.name}'. Planning roads TO its gates.")
                # --- ГЛАВНОЕ ИЗМЕНЕНИЕ ---
                # Удаляем ВСЕ дороги из самого чанка с городом
                if (cx, cz) in plan:
                    del plan[(cx, cz)]

                # Для каждого выхода из города...
                for side, exit_def in structure.exits.items():
                    # ...вычисляем координаты СОСЕДНЕГО чанка...
                    ncx, ncz = cx, cz
                    if side == 'N':
                        ncz -= 1
                    elif side == 'S':
                        ncz += 1
                    elif side == 'W':
                        ncx -= 1
                    elif side == 'E':
                        ncx += 1

                    # ...и добавляем ему в план дорогу, ведущую ОБРАТНО к городу.
                    opposite = OPPOSITE_SIDE[side]
                    plan.setdefault((ncx, ncz), []).append(opposite)

    # --- ЭТАП 3: ФИНАЛЬНАЯ ОЧИСТКА ---
    for coord, sides in plan.items():
        plan[coord] = sorted(list(dict.fromkeys(sides)))

    return plan