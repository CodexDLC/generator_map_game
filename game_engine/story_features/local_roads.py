# game_engine/story_features/local_roads.py
from __future__ import annotations
import random
from collections import deque
from typing import List, Dict, Tuple, Any
from opensimplex import OpenSimplex

# --- Импорты ---
from game_engine.algorithms.pathfinding.routers import BaseRoadRouter
from game_engine.algorithms.pathfinding.network import apply_paths_to_grid, find_path_network
from .road_helpers import (
    Coord, hub_anchor, find_edge_gate, make_local_road_policy,
)
from game_engine.core.constants import KIND_OBSTACLE, KIND_ROAD, KIND_WATER
from ..core.types import GenResult
from ..world_structure.regions import Region


def _choose_gate_sides(seed: int, cx: int, cz: int) -> List[str]:
    """
    Правила:
      - стартовый (1,0) -> ['W','E','N']  (к воротам, на восток, на север)
      - первые 5 чанков восточнее старта на оси z=0 (cx in [2..6], cz=0): без 'S'
      - прочие: 2..4 стороны детерминировано от мирового сида
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


def _side_of_gate(p: tuple[int, int], w: int, h: int) -> str:
    """Определяет сторону, на которой стоит гейт (ожидается отступ 1 клетка от края)."""
    x, z = p
    if z == 1: return 'N'
    if z == h - 2: return 'S'
    if x == 1: return 'W'
    if x == w - 2: return 'E'
    return '?'


def _carve_ramp_along_path(
        elev: list[list[float]],
        path: list[tuple[int, int]],
        *,
        ramp_step_m: float = 0.5,
        width: int = 3
) -> None:
    """
    Создает плавный пандус, "срезая" холмы, которые выше дороги.
    Аккуратнее на границах чанка.
    """
    if not path: return
    H, W = len(elev), len(elev[0]) if elev else 0
    if not (H and W): return

    path_heights = {pt: float(elev[pt[1]][pt[0]]) for pt in path}

    # сглаживание профиля туда-обратно
    for i in range(1, len(path)):
        p_prev, p_curr = path[i - 1], path[i]
        if abs(path_heights[p_curr] - path_heights[p_prev]) > ramp_step_m:
            path_heights[p_curr] = path_heights[p_prev] + ramp_step_m * (
                1 if path_heights[p_curr] > path_heights[p_prev] else -1)
    for i in range(len(path) - 2, -1, -1):
        p_next, p_curr = path[i + 1], path[i]
        if abs(path_heights[p_curr] - path_heights[p_next]) > ramp_step_m:
            path_heights[p_curr] = path_heights[p_next] + ramp_step_m * (
                1 if path_heights[p_curr] > path_heights[p_next] else -1)

    # ослабление к краям
    radius = (width - 1) // 2
    for (px, pz), target_h in path_heights.items():
        dist_to_border = min(px, pz, W - 1 - px, H - 1 - pz)
        strength = min(1.0, dist_to_border / 4.0)
        if strength <= 0: continue

        for dz in range(-radius, radius + 1):
            for dx in range(-radius, radius + 1):
                x, z = px + dx, pz + dz
                if 0 <= x < W and 0 <= z < H:
                    current_h = elev[z][x]
                    if current_h > target_h:
                        elev[z][x] = (current_h * (1 - strength)) + (target_h * strength)


def _preprocess_water_bodies(grid: List[List[str]], max_water_crossing_size: int):
    """
    Большие водоемы помечаем как OBSTACLE, чтобы их не пересекать дорогой.
    """
    h = len(grid)
    w = len(grid[0]) if h else 0
    if not (w and h): return

    visited = [[False for _ in range(w)] for _ in range(h)]

    for z in range(h):
        for x in range(w):
            if grid[z][x] == KIND_WATER and not visited[z][x]:
                water_body_tiles = []
                q = deque([(x, z)])
                visited[z][x] = True

                while q:
                    cx, cz = q.popleft()
                    water_body_tiles.append((cx, cz))
                    for dx, dz in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                        nx, nz = cx + dx, cz + dz
                        if 0 <= nx < w and 0 <= nz < h and \
                                not visited[nz][nx] and grid[nz][nx] == KIND_WATER:
                            visited[nz][nx] = True
                            q.append((nx, nz))

                if len(water_body_tiles) > max_water_crossing_size:
                    for wx, wz in water_body_tiles:
                        grid[wz][wx] = KIND_OBSTACLE


def _generate_temporary_obstacles(
        original_kind_grid: List[List[str]],
        seed: int,
        cx: int,
        cz: int,
        preset: Any
) -> List[List[str]]:
    """
    Делает копию карты и добавляет «призрачные» препятствия для маршрутизатора дорог.
    """
    temp_grid = [row[:] for row in original_kind_grid]
    size = len(temp_grid)

    scatter_cfg = getattr(preset, "scatter", {})
    if not scatter_cfg.get("enabled", False):
        return temp_grid

    road_obs_noise = OpenSimplex((seed ^ 0xCAFEFACE) & 0x7FFFFFFF)
    groups_cfg = scatter_cfg.get("groups", {})
    freq = 1.0 / float(groups_cfg.get("noise_scale_tiles", 32.0))
    threshold = float(groups_cfg.get("threshold", 0.55))

    for z in range(size):
        for x in range(size):
            if temp_grid[z][x] not in (KIND_ROAD,):
                wx, wz = cx * size + x, cz * size + z
                noise_val = (road_obs_noise.noise2(wx * freq, wz * freq) + 1.0) / 2.0
                if noise_val > threshold:
                    temp_grid[z][x] = KIND_OBSTACLE

    return temp_grid



# --- ОСНОВНАЯ ФУНКЦИЯ ---

def build_local_roads(
        result: GenResult,
        preset: Any,
        params: Dict,
        region: Region,
) -> None:
    """Строит дороги в чанке строго по плану region.road_plan[(cx,cz)]. + DEBUG-логи"""
    kind_grid = result.layers["kind"]
    height_grid = result.layers["height_q"]["grid"]
    size = result.size
    cx = params.get("cx", 0)
    cz = params.get("cz", 0)
    world_seed = params.get("seed", 0)

    # 1) Задание сторон
    sides_to_connect = region.road_plan.get((cx, cz), [])
    print(f"[ROADS] chunk=({cx},{cz}) size={size} sides={sides_to_connect}")
    if not sides_to_connect:
        print(f"[ROADS] ({cx},{cz}) no sides -> skip")
        return

    # 2) Поиск гейтов
    gates: List[tuple[int, int]] = []
    for side in sides_to_connect:
        p = find_edge_gate(kind_grid, side, cx, cz, size)
        print(f"[ROADS] ({cx},{cz}) side={side} gate={p}")
        if p:
            gates.append(p)

    if not gates:
        print(f"[ROADS] ({cx},{cz}) no gates found -> skip")
        return

    if len(gates) == 1:
        anchor = hub_anchor(kind_grid, preset) or (size // 2, size // 2)
        path = [gates[0], anchor]
        print(f"[ROADS] ({cx},{cz}) single gate={gates[0]} -> anchor={anchor}")
        apply_paths_to_grid(kind_grid, [path], width=2, allow_slope=True, allow_water=True)
        return

    # 3) Временная карта
    pathfinding_grid = [row[:] for row in kind_grid]  # только копия
    _preprocess_water_bodies(pathfinding_grid, max_water_crossing_size=4)
    print(f"[ROADS] ({cx},{cz}) temp obstacles: DISABLED")

    # 4) Точки
    points_to_connect = list(gates)
    if len(points_to_connect) >= 3:
        anchor = hub_anchor(kind_grid, preset)
        if anchor:
            points_to_connect.append(anchor)
            print(f"[ROADS] ({cx},{cz}) add hub anchor={anchor}")
    print(f"[ROADS] ({cx},{cz}) points_to_connect={points_to_connect}")

    # 5) Поиск сети
    policy = make_local_road_policy(slope_cost=50.0, water_cost=float('inf'))
    policy.terrain_factor[KIND_OBSTACLE] = float('inf')
    router = BaseRoadRouter(policy=policy)
    paths = find_path_network(pathfinding_grid, height_grid, points_to_connect, router)
    if not paths:
        print(f"[ROADS] ({cx},{cz}) no paths from router")
        return

    for i, p in enumerate(paths):
        if p:
            print(f"[ROADS] ({cx},{cz}) path#{i} len={len(p)} start={p[0]} end={p[-1]}")

    # 6) Дотянуть пути до края
    for gate in gates:
        side = _side_of_gate(gate, size, size)
        found = None
        for i, p in enumerate(paths):
            if p and (p[0] == gate or p[-1] == gate):
                found = (i, p[0] == gate)
                break
        if not found:
            print(f"[ROADS] ({cx},{cz}) gate {gate} not part of any path")
            continue

        i, at_start = found
        gx, gz = gate
        if side == 'N':
            ext = [(gx, z) for z in range(gz - 1, -1, -1)]
        elif side == 'S':
            ext = [(gx, z) for z in range(gz + 1, size)]
        elif side == 'W':
            ext = [(x, gz) for x in range(gx - 1, -1, -1)]
        elif side == 'E':
            ext = [(x, gz) for x in range(gx + 1, size)]
        else:
            print(f"[ROADS] ({cx},{cz}) gate {gate} side=? skip extend")
            continue

        print(f"[ROADS] ({cx},{cz}) extend path#{i} at_start={at_start} gate={gate} side={side} ext_len={len(ext)}")
        paths[i] = (ext + paths[i]) if at_start else (paths[i] + ext)



    # 7) Рендер
    print(f"[ROADS] ({cx},{cz}) apply {len(paths)} paths")
    apply_paths_to_grid(kind_grid, paths, width=2, allow_slope=True, allow_water=True)

    elev_cfg = getattr(preset, "elevation", {}) or {}
    ramp_step = float(elev_cfg.get("quantization_step_m", 0.5))
    for i, path in enumerate(paths):
        if height_grid and path:
            _carve_ramp_along_path(height_grid, path, ramp_step_m=ramp_step, width=4)
            print(f"[ROADS] ({cx},{cz}) carved ramp on path#{i} len={len(path)}")
