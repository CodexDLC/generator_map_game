# game_engine/core/utils/metrics.py
from __future__ import annotations
from typing import Any, Dict, List

from ..constants import KIND_VALUES, KIND_GROUND, KIND_OBSTACLE, KIND_WATER


def compute_metrics(kind_grid: List[List[str]]) -> Dict[str, float]:
    h = len(kind_grid);
    w = len(kind_grid[0]) if h else 0
    total = h * w if h else 0
    if total == 0: return {"open_pct": 0.0, "obstacle_pct": 0.0, "water_pct": 0.0}

    counts = {k: 0 for k in KIND_VALUES}
    for row in kind_grid:
        for v in row:
            counts[v] = counts.get(v, 0) + 1

    open_cells = counts.get(KIND_GROUND, 0)
    obstacle_cells = counts.get(KIND_OBSTACLE, 0)
    water_cells = counts.get(KIND_WATER, 0)

    return {
        "open_pct": open_cells / total,
        "obstacle_pct": obstacle_cells / total,
        "water_pct": water_cells / total,
    }