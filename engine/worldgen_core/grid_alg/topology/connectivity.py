# engine/worldgen_core/grid_alg/topology/connectivity.py
from __future__ import annotations
from typing import Dict, Any, List, Tuple, Set

from engine.worldgen_core.base.constants import KIND_GROUND
from engine.worldgen_core.base.rng import RNG, edge_key
from engine.worldgen_core.grid_alg.topology.border import side_neighbor


# --- Вспомогательные функции (Шаги 1-4) ---

def _find_best_port_position(rng: RNG, side: str, size: int, margin: int, kind_grid: List[List[str]]) -> int:
    """Шаг 1: Находит лучшую проходимую точку для порта на одной стороне."""
    positions = list(range(margin, size - margin))
    rng.shuffle(positions)

    for pos in positions:
        # Проверяем северную границу (строка 0)
        if side == "N" and kind_grid[0][pos] == KIND_GROUND: return pos
        # Проверяем южную границу (последняя строка)
        if side == "S" and kind_grid[size - 1][pos] == KIND_GROUND: return pos
        # Проверяем западную границу (столбец 0)
        if side == "W" and kind_grid[pos][0] == KIND_GROUND: return pos
        # Проверяем восточную границу (последний столбец) - ИСПРАВЛЕНО
        if side == "E" and kind_grid[pos][size - 1] == KIND_GROUND: return pos

    # Если ничего не нашли, возвращаем случайную позицию
    return positions[0]

def _calculate_initial_candidates(seed: int, cx: int, cz: int, size: int, margin: int, kind_grid: List[List[str]]) -> \
Tuple[Dict[str, int], Dict[str, int]]:
    """Шаг 2: Рассчитывает веса (хеши) и позиции-кандидаты для всех сторон."""
    sides = ["N", "E", "S", "W"]
    hashes: Dict[str, int] = {}
    positions: Dict[str, int] = {}

    for side in sides:
        nx, nz = side_neighbor(cx, cz, side)
        rng = RNG(edge_key(seed, cx, cz, nx, nz))
        hashes[side] = rng.u32()
        positions[side] = _find_best_port_position(rng, side, size, margin, kind_grid)

    return hashes, positions


def _apply_branch_rules(seed: int, cx: int, cz: int, params: Dict[str, Any]) -> Set[str]:
    """Шаг 3: Определяет "желаемые" активные порты на основе логики ветвей."""
    world_id = str(params.get("world_id", "city"))
    if not world_id.startswith("branch/"):
        return set()

    sides = ["N", "E", "S", "W"]
    opposite = {"N": "S", "S": "N", "W": "E", "E": "W"}
    branch_side = world_id.split('/', 1)[1]
    bias = float(params.get("branch_bias", 0.3))
    active_ports = set()

    for side in sides:
        rng = RNG(edge_key(seed, cx, cz, *side_neighbor(cx, cz, side)))
        is_active = False
        if side == branch_side:  # Вперед по ветке
            is_active = rng.uniform() < (0.6 + bias)
        elif side != opposite[branch_side]:  # Вбок от ветки
            is_active = rng.uniform() < (0.1 + bias / 2)
        else:  # Назад к началу ветки
            is_active = rng.uniform() < 0.5

        if is_active:
            active_ports.add(side)

    return active_ports


def _ensure_minimum_connectivity(active_ports: Set[str], hashes: Dict[str, int], params: Dict[str, Any]) -> None:
    """Шаг 4: Гарантирует, что у чанка есть минимальное кол-во выходов."""
    world_id = str(params.get("world_id", "city"))
    min_ports = 1 if world_id.startswith("branch/") else 2

    if len(active_ports) < min_ports:
        # Сортируем стороны по весу, чтобы гарантировать одинаковый результат у соседей
        sorted_sides = sorted(hashes.keys(), key=lambda s: hashes[s])

        for side in sorted_sides:
            if len(active_ports) >= min_ports:
                break
            active_ports.add(side)  # Добавляем самые "весомые" из еще неактивных


# --- Главная функция-"дирижер" ---

def choose_ports(seed: int, cx: int, cz: int, size: int, cfg: Dict[str, Any], params: Dict[str, Any],
                 kind_grid: List[List[str]]) -> Dict[str, List[int]]:
    """
    Определяет активные порты, координируя работу вспомогательных функций.
    """
    margin = int(cfg.get("edge_margin", 3))

    # 1. Рассчитать всех кандидатов
    hashes, positions = _calculate_initial_candidates(seed, cx, cz, size, margin, kind_grid)

    # 2. Определить "желаемые" порты по правилам мира (например, для веток)
    active_ports = _apply_branch_rules(seed, cx, cz, params)

    # 3. Убедиться, что портов не меньше минимума
    _ensure_minimum_connectivity(active_ports, hashes, params)

    # 4. Сформировать итоговый результат
    result: Dict[str, List[int]] = {s: [] for s in ["N", "E", "S", "W"]}
    for side in active_ports:
        result[side] = [positions[side]]

    return result