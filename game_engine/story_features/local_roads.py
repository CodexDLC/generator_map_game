# game_engine/story_features/local_roads.py
from __future__ import annotations
import random
from typing import List, Optional, Dict, Tuple, Any
from opensimplex import OpenSimplex

# --- Импорты ---
from game_engine.algorithms.pathfinding.routers import BaseRoadRouter
from game_engine.algorithms.pathfinding.network import apply_paths_to_grid
from .road_helpers import (
    Coord, hub_anchor, find_edge_gate, make_local_road_policy,
)
from game_engine.core.constants import KIND_GROUND, KIND_SAND, KIND_OBSTACLE, KIND_ROAD



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
    Подрезаем только резкие перепады высот вдоль дороги.
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

    x0, z0 = path[0]
    prev_h = float(elev[z0][x0])

    for (x, z) in path[1:]:
        orig = float(elev[z][x])
        dh = orig - prev_h

        if abs(dh) <= step_m + eps:
            prev_h = orig
            continue

        target = prev_h + (step_m if dh > 0 else -step_m)

        if is_road(x, z):
            elev[z][x] = target
        for dz in range(-r, r + 1):
            for dx in range(-r, r + 1):
                if max(abs(dx), abs(dz)) <= r and is_road(x + dx, z + dz):
                    elev[z + dz][x + dx] = target
        prev_h = target

# --- НАЧАЛО НОВОЙ ЛОГИКИ ---

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
    freq = 1.0 / float(groups_cfg.get("noise_scale_tiles", 48.0))  # Чуть более мелкие пятна
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
        result: "GenResult",  # Теперь принимаем весь результат генерации
        preset: Any,
        params: Dict,
        *,
        width: int = 1,
) -> None:
    """
    Прокладка дорог ВНУТРИ одного чанка с использованием временного "слепка".
    """
    kind_grid = result.layers["kind"]
    height_grid = result.layers["height_q"]["grid"]
    size = result.size
    cx = params.get("cx", 0)
    cz = params.get("cz", 0)
    world_seed = params.get("seed", 0)

    # 1. Создаем временный "слепок" с призрачными препятствиями
    pathfinding_grid = _generate_temporary_obstacles(kind_grid, world_seed, cx, cz, preset)

    # 2. Определяем цели для дорог (центральный хаб и выходы)
    anchor = hub_anchor(kind_grid, preset)
    sides = _choose_gate_sides(world_seed, cx, cz)
    if not sides:
        return

    gates: List[Coord] = []
    for s in sides:
        p = find_edge_gate(kind_grid, s, cx, cz, size)
        if p:
            # "Пробиваем" препятствия у ворот на временной карте
            pathfinding_grid[p[1]][p[0]] = KIND_GROUND
            gates.append(p)
    if not gates:
        return

    # 3. Настраиваем A* так, чтобы он мог проходить через препятствия, но с большим штрафом
    # Это позволит ему "пробивать" пятна, если нет другого пути.
    policy = make_local_road_policy(slope_cost=2.0, water_cost=15.0)
    policy.terrain_factor[KIND_OBSTACLE] = 25.0  # Очень дорого, но не бесконечно!
    router = BaseRoadRouter(policy=policy)

    # 4. Ищем пути на ВРЕМЕННОЙ карте
    paths: List[List[Coord]] = []
    for gate in gates:
        # Ищем путь от якоря до ворот на карте с препятствиями
        path = router.find(pathfinding_grid, height_grid, anchor, gate)
        if path:
            paths.append(path)

    if not paths:
        return

    # 5. Применяем найденные пути к НАСТОЯЩЕЙ карте
    apply_paths_to_grid(
        kind_grid,  # <--- Применяем к оригиналу!
        paths,
        width=max(1, int(width)),
        allow_slope=True,
        allow_water=True  # Разрешаем строить мосты/броды
    )

    # 6. Прорезаем пандусы (старая логика, можно улучшать в будущем)
    elev_cfg = getattr(preset, "elevation", {}) or {}
    ramp_step = float(elev_cfg.get("quantization_step_m", 1.0))
    for path in paths:
        if height_grid:
            _carve_ramp_along_path(
                height_grid, path,
                step_m=ramp_step,
                width=max(1, int(width)),
                kind=kind_grid,
            )