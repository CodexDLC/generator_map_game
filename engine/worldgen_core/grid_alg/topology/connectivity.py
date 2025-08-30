# engine/worldgen_core/grid_alg/topology/connectivity.py
from __future__ import annotations
from typing import Dict, Any, List, Tuple, Set

from engine.worldgen_core.base.constants import KIND_GROUND
from engine.worldgen_core.base.rng import RNG, edge_key
from engine.worldgen_core.grid_alg.topology.border import side_neighbor
from engine.worldgen_core.grid_alg.topology.metrics import sample_neighbor_border


def _get_local_border_passability(side: str, kind_grid: List[List[str]]) -> List[bool]:
    """Возвращает маску проходимости для своей собственной границы."""
    size = len(kind_grid)
    pass_mask = [False] * size
    if side == "N":
        for i in range(size): pass_mask[i] = (kind_grid[0][i] == KIND_GROUND)
    elif side == "S":
        for i in range(size): pass_mask[i] = (kind_grid[size - 1][i] == KIND_GROUND)
    elif side == "W":
        for i in range(size): pass_mask[i] = (kind_grid[i][0] == KIND_GROUND)
    elif side == "E":
        for i in range(size): pass_mask[i] = (kind_grid[i][size - 1] == KIND_GROUND)
    return pass_mask


def _find_shared_port_position(
        rng: RNG, margin: int, size: int,
        local_pass_mask: List[bool],
        neighbor_pass_mask: List[bool]
) -> int | None:
    """Находит общую проходимую точку на границе."""
    possible_positions = []
    for i in range(margin, size - margin):
        if local_pass_mask[i] and neighbor_pass_mask[i]:
            possible_positions.append(i)

    if not possible_positions:
        return None  # Нет общих точек

    rng.shuffle(possible_positions)
    return possible_positions[0]


def choose_ports(
        result: 'GenResult',
        cfg: Dict[str, Any],
        params: Dict[str, Any],
        obs_cfg: Dict[str, Any],
        wat_cfg: Dict[str, Any]
) -> Dict[str, List[int]]:
    """
    Определяет порты на основе "согласования" с соседями.
    """
    margin = int(cfg.get("edge_margin", 3))
    seed, cx, cz, size = result.seed, result.cx, result.cz, result.size
    kind_grid = result.layers["kind"]
    stage_seeds = result.stage_seeds

    ports: Dict[str, List[int]] = {s: [] for s in ["N", "E", "S", "W"]}
    sides = ["N", "E", "S", "W"]

    # Сначала определяем, на каких сторонах В ПРИНЦИПЕ могут быть порты
    # (по правилам веток, например)
    # Эта логика упрощена, можно вернуть _apply_branch_rules при желании
    active_sides = set()
    world_id = str(params.get("world_id", "city"))
    if world_id.startswith("branch/"):
        # В ветках всегда есть как минимум один порт
        num_ports = RNG(seed ^ cx ^ cz).randint(1, 3)
        shuffled_sides = list(sides)
        RNG(seed ^ cx ^ cz).shuffle(shuffled_sides)
        active_sides.update(shuffled_sides[:num_ports])
    else:  # В обычном мире 2-4 порта
        num_ports = RNG(seed ^ cx ^ cz).randint(2, 4)
        shuffled_sides = list(sides)
        RNG(seed ^ cx ^ cz).shuffle(shuffled_sides)
        active_sides.update(shuffled_sides[:num_ports])

    # Теперь для каждой активной стороны пытаемся "договориться" с соседом о месте
    for side in active_sides:
        nx, nz = side_neighbor(cx, cz, side)
        edge_rng = RNG(edge_key(seed, cx, cz, nx, nz))

        # 1. Получаем проходимость своей границы
        local_pass_mask = _get_local_border_passability(side, kind_grid)

        # 2. Получаем проходимость границы соседа
        neighbor_tiles = sample_neighbor_border(side, cx, cz, size, stage_seeds, obs_cfg, wat_cfg)
        neighbor_pass_mask = [tile_id == 0 for tile_id in neighbor_tiles]

        # 3. Ищем общую точку
        position = _find_shared_port_position(edge_rng, margin, size, local_pass_mask, neighbor_pass_mask)

        if position is not None:
            ports[side] = [position]

    return ports