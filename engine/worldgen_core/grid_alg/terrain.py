# engine/worldgen_core/grid_alg/terrain.py

from __future__ import annotations
from typing import Any, List

from .features import fbm2d
from ..base.constants import KIND_OBSTACLE, KIND_WATER, KIND_GROUND


def generate_elevation(seed: int, cx: int, cz: int, size: int) -> List[List[float]]:
    """Создает базовую карту высот для всего чанка."""
    grid = [[0.0 for _ in range(size)] for _ in range(size)]
    freq = 1.0 / 32.0  # Масштаб холмов
    for z in range(size):
        for x in range(size):
            wx, wz = cx * size + x, cz * size + z
            # Используем FBM шум для создания естественного рельефа
            grid[z][x] = fbm2d(seed, float(wx), float(wz), freq, octaves=4, gain=0.5)
    return grid


def classify_terrain(
        elevation_grid: List[List[float]],
        kind_grid: List[List[str]],
        preset: Any
) -> None:
    """Заполняет kind_grid типами ландшафта на основе высот."""
    size = len(kind_grid)

    # Уровни можно будет настроить в пресете
    sea_level = 0.35
    mountain_level = 0.65

    # Пытаемся получить значения из пресета, если он есть
    if preset:
        sea_level = float(getattr(preset, "sea_level", sea_level))
        mountain_level = float(getattr(preset, "mountain_level", mountain_level))

    for z in range(size):
        for x in range(size):
            elev = elevation_grid[z][x]
            if elev < sea_level:
                kind_grid[z][x] = KIND_WATER
            elif elev > mountain_level:
                kind_grid[z][x] = KIND_OBSTACLE
            else:
                kind_grid[z][x] = KIND_GROUND