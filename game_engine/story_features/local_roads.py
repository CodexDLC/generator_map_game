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
      - первые 5 Чанков восточнее старта на оси z=0 (cx in [2..6], cz=0): без 'S'
      - прочие: 2..4 стороны детерминированною от мирового сида
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


def _side_of_gate(p: tuple[int,int], w: int, h: int) -> str:
    """Определяет, на какой стороне находится гейт."""
    x, z = p
    # Гейт ставится с отступом в 1 клетку от края
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
    Теперь работает аккуратнее на границах чанка.
    """
    if not path: return
    H, W = len(elev), len(elev[0]) if elev else 0
    if not (H and W): return

    path_heights = {pt: float(elev[pt[1]][pt[0]]) for pt in path}

    # Сглаживаем профиль высот дороги (вперед и назад)
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

    # Применяем "земляные работы", ослабляя эффект у краев
    radius = (width - 1) // 2
    for (px, pz), target_h in path_heights.items():
        # Определяем, насколько мы близки к границе
        dist_to_border = min(px, pz, W - 1 - px, H - 1 - pz)
        # Сила воздействия: 100% в центре, плавно падает до 0% на границе
        strength = min(1.0, dist_to_border / 4.0)
        if strength <= 0: continue

        for dz in range(-radius, radius + 1):
            for dx in range(-radius, radius + 1):
                x, z = px + dx, pz + dz
                if 0 <= x < W and 0 <= z < H:
                    current_h = elev[z][x]
                    # Применяем сглаживание только если нужно и с учетом силы
                    if current_h > target_h:
                        elev[z][x] = (current_h * (1 - strength)) + (target_h * strength)


def _preprocess_water_bodies(grid: List[List[str]], max_water_crossing_size: int):
    """
    Находит на карте водоемы. Если водоем большой, помечает его как OBSTACLE,
    чтобы A* не мог через него пройти.
    """
    h = len(grid)
    w = len(grid[0]) if h else 0
    if not (w and h): return

    visited = [[False for _ in range(w)] for _ in range(h)]

    for z in range(h):
        for x in range(w):
            if grid[z][x] == KIND_WATER and not visited[z][x]:
                # Нашли новый, еще не изученный водоем. Начинаем поиск в ширину (BFS).
                water_body_tiles = []
                q = deque([(x, z)])
                visited[z][x] = True

                while q:
                    cx, cz = q.popleft()
                    water_body_tiles.append((cx, cz))

                    # Проверяем 4-х соседей
                    for dx, dz in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                        nx, nz = cx + dx, cz + dz
                        if 0 <= nx < w and 0 <= nz < h and \
                                not visited[nz][nx] and grid[nz][nx] == KIND_WATER:
                            visited[nz][nx] = True
                            q.append((nx, nz))

                # Если размер водоема превышает лимит, делаем его непроходимым
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
    Создает "слепок" карты и рисует на нем призрачные препятствия для дорог.
    """
    # 1. Создаем глубокую копию, чтобы не портить оригинал
    temp_grid = [row[:] for row in original_kind_grid]
    size = len(temp_grid)

    scatter_cfg = getattr(preset, "scatter", {})
    if not scatter_cfg.get("enabled", False):
        return temp_grid  # Возвращаем копию без изменений, если функция отключена

    # 2. Используем свой, отдельный шум для дорожных препятствий, чтобы он был бесшовным
    road_obs_noise = OpenSimplex((seed ^ 0xCAFEFACE) & 0x7FFFFFFF)
    groups_cfg = scatter_cfg.get("groups", {})
    freq = 1.0 / float(groups_cfg.get("noise_scale_tiles", 32.0))  # Чуть более мелкие пятна
    threshold = float(groups_cfg.get("threshold", 0.55))

    for z in range(size):
        for x in range(size):
            # Мы можем рисовать препятствия даже поверх деревьев на временной карте
            if temp_grid[z][x] not in (KIND_ROAD,):  # Не трогаем только уже существующие дороги
                wx, wz = cx * size + x, cz * size + z
                noise_val = (road_obs_noise.noise2(wx * freq, wz * freq) + 1.0) / 2.0
                if noise_val > threshold:
                    temp_grid[z][x] = KIND_OBSTACLE

    return temp_grid


# --- ОСНОВНАЯ ФУНКЦИЯ, ПЕРЕРАБОТАННАЯ ---

def build_local_roads(
        result: GenResult,
        preset: Any,
        params: Dict,
        region: Region,
) -> None:
    """
    Строит дороги в чанке, СТРОГО СЛЕДУЯ плану, полученному от RegionManager.
    """
    kind_grid = result.layers["kind"]
    height_grid = result.layers["height_q"]["grid"]
    size = result.size
    cx = params.get("cx", 0)
    cz = params.get("cz", 0)
    # --- НАЧАЛО ИЗМЕНЕНИЯ (1/2): Получаем world_seed из правильного места ---
    world_seed = params.get("seed", 0)
    # --- КОНЕЦ ИЗМЕНЕНИЯ ---

    # 1. Получаем "задание" для этого конкретного чанка из глобального плана
    sides_to_connect = region.road_plan.get((cx, cz), [])

    print(f"--- [DEBUG] Чанк ({cx},{cz}) получил задание на дороги: {sides_to_connect}")

    if not sides_to_connect:
        return

    # 2. Находим на карте точки-ворота, соответствующие плану
    gates = []
    for side in sides_to_connect:
        p = find_edge_gate(kind_grid, side, cx, cz, size)
        if p:
            gates.append(p)

    if len(gates) < 2:
        return

    # 3. Создаем временную карту для поиска пути (как и раньше)
    # --- НАЧАЛО ИЗМЕНЕНИЯ (2/2): Используем правильную переменную world_seed ---
    pathfinding_grid = _generate_temporary_obstacles(kind_grid, world_seed, cx, cz, preset)
    # --- КОНЕЦ ИЗМЕНЕНИЯ ---
    _preprocess_water_bodies(pathfinding_grid, max_water_crossing_size=4)

    # 4. В зависимости от количества выходов, решаем, нужен ли перекресток
    points_to_connect = list(gates)
    num_exits = len(points_to_connect)

    # Ваша логика: если выходов 3 или больше, ищем центр для перекрестка
    if num_exits >= 3:
        anchor = hub_anchor(kind_grid, preset)
        if anchor:
            points_to_connect.append(anchor)

    # 5. Находим оптимальную сеть, соединяющую все нужные точки
    policy = make_local_road_policy(slope_cost=50.0, water_cost=float('inf'))
    policy.terrain_factor[KIND_OBSTACLE] = 75.0
    router = BaseRoadRouter(policy=policy)

    paths = find_path_network(pathfinding_grid, height_grid, points_to_connect, router)

    if not paths:
        return

    # --- НОВЫЙ БЛОК: "Дотягиваем" пути до края чанка ---
    # Это решает проблему разрывов на границах.
    all_points_on_paths = {point for path in paths for point in path}
    for gate in gates:
        if gate in all_points_on_paths:
            side = _side_of_gate(gate, size, size) # Нужна вспомогательная функция
            path_to_extend = next((p for p in paths if p and p[-1] == gate), None)
            if path_to_extend:
                if side == 'N': path_to_extend.insert(0, (gate[0], 0))
                elif side == 'S': path_to_extend.append((gate[0], size - 1))
                elif side == 'W': path_to_extend.insert(0, (0, gate[1]))
                elif side == 'E': path_to_extend.append((size - 1, gate[1]))

    # 7. Рисуем дороги и пандусы (без изменений)
    apply_paths_to_grid(kind_grid, paths, width=2, allow_slope=True, allow_water=True)

    elev_cfg = getattr(preset, "elevation", {}) or {}
    ramp_step = float(elev_cfg.get("quantization_step_m", 0.5))
    for path in paths:
        if height_grid:
            _carve_ramp_along_path(height_grid, path, ramp_step_m=ramp_step, width=4)