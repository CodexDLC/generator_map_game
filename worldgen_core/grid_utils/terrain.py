# worldgen_core/grid_utils/terrain.py
from __future__ import annotations
from typing import Iterable
from math import inf
from opensimplex import OpenSimplex

from .core import TILE
from .topology import neighbors4

def _manhattan(a: tuple[int,int], b: tuple[int,int]) -> int:
    return abs(a[0]-b[0]) + abs(a[1]-b[1])

def _mask_manhattan(w: int, h: int, centers: Iterable[tuple[int,int]], radius: int) -> set[tuple[int,int]]:
    if radius <= 0:
        return set()
    out: set[tuple[int,int]] = set()
    for cx, cy in centers:
        for y in range(max(0, cy - radius), min(h, cy + radius + 1)):
            dy = abs(y - cy)
            span = radius - dy
            if span < 0:
                continue
            x0 = max(0, cx - span)
            x1 = min(w - 1, cx + span)
            for x in range(x0, x1 + 1):
                out.add((x, y))
    return out

def paint_road_on_path(grid: list[list[int]], path: list[tuple[int,int]], width: int = 3) -> set[tuple[int,int]]:
    """
    Помечает клетки вдоль пути тайлом ROAD с заданной шириной (манхэттен).
    Возвращает множество окрашенных клеток.
    """
    if not path:
        return set()
    k = max(0, (width - 1) // 2)
    H, W = len(grid), len(grid[0])
    painted: set[tuple[int,int]] = set()
    for x, y in path:
        for dx in range(-k, k + 1):
            for dy in range(-k, k + 1):
                if abs(dx) + abs(dy) <= k:
                    nx, ny = x + dx, y + dy
                    if 0 <= nx < W and 0 <= ny < H:
                        if grid[ny][nx] == TILE["FLOOR"]:
                            grid[ny][nx] = TILE["ROAD"]
                            painted.add((nx, ny))
    return painted

def _is_neck(grid: list[list[int]], x: int, y: int) -> bool:
    """
    «Горлышко»: у клетки меньше 2 соседей типа FLOOR/ROAD в 4-соседстве.
    """
    H, W = len(grid), len(grid[0])
    n = 0
    for nx, ny in neighbors4(x, y, W, H):
        if grid[ny][nx] in (TILE["FLOOR"], TILE["ROAD"]):
            n += 1
    return n < 2

def apply_biomes(
    grid: list[list[int]],
    seed: int,
    weights: dict[str, float] | None,
    *,
    safe_centers: list[tuple[int,int]] | None = None,
    safe_radius: int = 3,
    no_mountain_in_necks: bool = True,
) -> None:
    """
    Раскрашивает оставшийся FLOOR в {GRASS, FOREST, MOUNTAIN} по весам.
    ROAD/WALL/WATER/BORDER не трогаем.
    """
    W = len(grid[0]); H = len(grid)
    if not weights:
        weights = {"grass": 0.45, "forest": 0.30, "mountain": 0.15}

    # Кандидаты: только FLOOR
    candidates: list[tuple[int,int]] = [(x, y) for y in range(H) for x in range(W) if grid[y][x] == TILE["FLOOR"]]
    if not candidates:
        return

    # Зона безопасности у ворот/комнат
    avoid_mask: set[tuple[int,int]] = set()
    if safe_centers:
        avoid_mask |= _mask_manhattan(W, H, safe_centers, safe_radius)

    # Фильтруем кандидатов
    cand = [(x, y) for (x, y) in candidates if (x, y) not in avoid_mask]
    if not cand:
        return

    # Нормализация весов
    w_grass = max(0.0, float(weights.get("grass", 0.0)))
    w_forest = max(0.0, float(weights.get("forest", 0.0)))
    w_mtn = max(0.0, float(weights.get("mountain", 0.0)))
    s = w_grass + w_forest + w_mtn
    if s <= 1e-9:
        return
    w_grass /= s; w_forest /= s; w_mtn /= s

    total = len(cand)
    target_mtn = int(total * w_mtn)
    target_forest = int(total * w_forest)
    target_grass = int(total * w_grass)  # остаток и так останется floor, но часть хотим покрасить в grass

    # Шумы для кластеров
    n_mtn = OpenSimplex(seed=seed ^ 0xAA5511)
    n_for = OpenSimplex(seed=seed ^ 0x22BEEF)
    n_grs = OpenSimplex(seed=seed ^ 0x333777)
    scale_mtn = 18.0
    scale_for = 12.0
    scale_grs = 10.0

    def score_mtn(x: int, y: int) -> float:
        v = (n_mtn.noise2(x / scale_mtn, y / scale_mtn) + 1) * 0.5
        if no_mountain_in_necks and _is_neck(grid, x, y):
            v -= 1.0  # жёстко штрафуем «горлышки»
        return v

    def score_for(x: int, y: int) -> float:
        return (n_for.noise2(x / scale_for, y / scale_for) + 1) * 0.5

    def score_grs(x: int, y: int) -> float:
        return (n_grs.noise2(x / scale_grs, y / scale_grs) + 1) * 0.5

    # Выбор по убыванию скоров
    cand_mtn = sorted(cand, key=lambda p: score_mtn(p[0], p[1]), reverse=True)[:target_mtn]
    used = set(cand_mtn)
    for x, y in cand_mtn:
        grid[y][x] = TILE["MOUNTAIN"]

    remain = [p for p in cand if p not in used]
    cand_for = sorted(remain, key=lambda p: score_for(p[0], p[1]), reverse=True)[:target_forest]
    used.update(cand_for)
    for x, y in cand_for:
        grid[y][x] = TILE["FOREST"]

    remain = [p for p in remain if p not in used]
    cand_grs = sorted(remain, key=lambda p: score_grs(p[0], p[1]), reverse=True)[:target_grass]
    for x, y in cand_grs:
        grid[y][x] = TILE["GRASS"]
