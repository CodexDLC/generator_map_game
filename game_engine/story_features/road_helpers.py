# game_engine/story_features/road_helpers.py
from __future__ import annotations
from typing import List, Tuple, Optional, Iterator
from collections import deque # <-- Добавляем импорт для _preprocess_water_bodies

# --- Централизованные и согласованные импорты ---
from game_engine.algorithms.pathfinding.helpers import Coord
from game_engine.core.constants import (
    KIND_GROUND, KIND_WATER, KIND_SLOPE, KIND_ROAD, KIND_SAND, KIND_OBSTACLE
)
from .story_definitions import get_structure_at



def side_of_gate(p: tuple[int, int], w: int, h: int) -> str:
    """Определяет сторону, на которой стоит гейт (ожидается отступ 1 клетка от края)."""
    x, z = p
    if z == 1: return 'N'
    if z == h - 2: return 'S'
    if x == 1: return 'W'
    if x == w - 2: return 'E'
    return '?'


def carve_ramp_along_path(
        elev: list[list[float]],
        path: list[tuple[int, int]],
        *,
        ramp_step_m: float = 0.5,
        width: int = 3
) -> None:
    """
    Создает плавный пандус, "срезая" холмы, которые выше дороги.
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


def preprocess_water_bodies(grid: List[List[str]], max_water_crossing_size: int):
    """
    Большие водоемы (больше max_water_crossing_size) помечаем как OBSTACLE.
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

# --- КОНЕЦ ПЕРЕНЕСЕННОГО КОДА ---
# ------------------------- площадка/якорь «хаба» -------------------------
def hub_rect(size: int, preset) -> tuple[int, int, int, int]:
    cfg_hp = getattr(preset, "hub_pad", {}) or {}
    if cfg_hp.get("enabled", False):
        pad = max(1, int(cfg_hp.get("size_tiles", 3)))
        c = size // 2
        x0 = max(0, c - pad // 2)
        x1 = min(size, x0 + pad)
        z0 = max(0, c - pad // 2)
        z1 = min(size, z0 + pad)
        return x0, z0, x1, z1
    return size // 3, size // 3, (2 * size) // 3, (2 * size) // 3


def hub_anchor(kind: List[List[str]], preset) -> Optional[Coord]:
    """
    Находит лучшую точку для центрального перекрестка, ИГНОРИРУЯ воду.
    Возвращает None, если в центре нет подходящей земли.
    """
    h = len(kind)
    w = len(kind[0]) if h else 0
    x0, z0, x1, z1 = hub_rect(w, preset)
    cx = (x0 + x1) // 2
    cz = (z0 + z1) // 2

    def rank(k: str) -> int:
        if k in (KIND_GROUND, KIND_SAND): return 0
        if k == KIND_SLOPE: return 1
        return 9999

    best: Optional[Coord] = None
    best_score = 10 ** 9
    for z in range(z0, z1):
        for x in range(x0, x1):
            k = kind[z][x]
            r = rank(k)
            if r >= 9999: continue
            d = abs(x - cx) + abs(z - cz)
            s = r * 10000 + d
            if s < best_score:
                best_score = s
                best = (x, z)
    return best


# ------------------------- итераторы по граням -------------------------
def _iter_from_center(center: int, max_val: int, inset: int) -> Iterator[int]:
    """Итерирует по координатам вдоль одной оси, начиная от центра."""
    max_dist = max(center - inset, max_val - 1 - inset - center)
    for d in range(max_dist + 1):
        p1 = center - d
        if inset <= p1 < max_val - inset: yield p1
        p2 = center + d
        if d != 0 and inset <= p2 < max_val - inset: yield p2


def _scan_edge_from_center(side: str, w: int, h: int, inset: int = 1):
    """Итератор по клеткам на грани, начиная от центра к краям."""
    xc, zc = w // 2, h // 2
    if side in ("N", "S"):
        z = inset if side == "N" else h - 1 - inset
        for x in _iter_from_center(xc, w, inset): yield x, z
    elif side in ("W", "E"):
        x = inset if side == "W" else w - 1 - inset
        for z in _iter_from_center(zc, h, inset): yield x, z


# ------------------------- выбор «гейта» на грани чанка -------------------------
def _passable_for_gate(kind: str) -> bool:
    """Определяет, можно ли в тайле такого типа разместить "ворота" для дороги."""
    return kind in (KIND_GROUND, KIND_SLOPE, KIND_ROAD, KIND_SAND)


def find_edge_gate(kind_grid: List[List[str]], side: str,
                   cx: int, cz: int, size: int) -> Optional[Coord]:
# --- КОНЕЦ ИЗМЕНЕНИЯ ---
    """Возвращает точку гейта на нашей границе; если у соседа-строения
    нет выхода на нас — возвращает None и запрещает fallback-сканирование."""

    OPPOSITE = {'N': 'S', 'S': 'N', 'W': 'E', 'E': 'W'}
    DIR = {'N': (0, -1), 'S': (0, 1), 'W': (-1, 0), 'E': (1, 0)}

    h = len(kind_grid)
    w = len(kind_grid[0]) if h else 0
    if not (w and h):
        return None

    # сосед по стороне
    dx, dz = DIR[side]
    n_cx, n_cz = cx + dx, cz + dz
    neighbor = get_structure_at(n_cx, n_cz)

    # если сосед — строение БЕЗ выхода на нас → гейта нет и fallback запрещён
    if neighbor and OPPOSITE[side] not in neighbor.exits:
        return None

    # если у соседа есть выход на нас → зеркалим его позицию
    if neighbor and OPPOSITE[side] in neighbor.exits:
        pos = int(size * neighbor.exits[OPPOSITE[side]].position_percent / 100)
        pos = max(1, min(w - 2, pos))
        if side == 'N': return pos, 1
        if side == 'S': return pos, h - 2
        if side == 'W': return 1,   pos
        if side == 'E': return w - 2, pos

    # обычный случай: ищем готовую дорогу или проходимую клетку на нашей кромке
    for x, z in _scan_edge_from_center(side, w, h, inset=1):
        if kind_grid[z][x] == KIND_ROAD:
            return (x, z)
    for x, z in _scan_edge_from_center(side, w, h, inset=1):
        if _passable_for_gate(kind_grid[z][x]):
            return (x, z)

    return None


def _bridge_streak_over(kind: List[List[str]], path: List[Tuple[int,int]], limit: int) -> bool:
    cnt = 0
    for x, z in path:
        if kind[z][x] == KIND_WATER:
            cnt += 1
            if cnt > limit:
                return True
        else:
            cnt = 0
    return False