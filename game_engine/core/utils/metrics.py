# game_engine/core/utils/metrics.py
from __future__ import annotations
from typing import Dict, List

# --- ИЗМЕНЕНИЕ: Импортируем нужные константы из новых наборов ---
from ..constants import KIND_GROUND, NAV_OBSTACLE, NAV_WATER


def compute_metrics(surface_grid: List[List[str]], nav_grid: List[List[str]]) -> Dict[str, float]:
    """
    Считает метрики по чанку, используя оба слоя: surface и navigation.
    """
    h = len(surface_grid)
    w = len(surface_grid[0]) if h else 0
    total = h * w
    if total == 0:
        return {"open_pct": 0.0, "obstacle_pct": 0.0, "water_pct": 0.0}

    # Считаем количество разных типов в каждом слое
    surface_counts: Dict[str, int] = {}
    for row in surface_grid:
        for v in row:
            surface_counts[v] = surface_counts.get(v, 0) + 1

    nav_counts: Dict[str, int] = {}
    for row in nav_grid:
        for v in row:
            nav_counts[v] = nav_counts.get(v, 0) + 1

    # "Открытые" клетки - это земля на слое поверхностей
    open_cells = surface_counts.get(KIND_GROUND, 0)
    # Препятствия и вода - на навигационном слое
    obstacle_cells = nav_counts.get(NAV_OBSTACLE, 0)
    water_cells = nav_counts.get(NAV_WATER, 0)

    return {
        "open_pct": open_cells / total,
        "obstacle_pct": obstacle_cells / total,
        "water_pct": water_cells / total,
    }