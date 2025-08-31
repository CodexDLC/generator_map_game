# engine/worldgen_core/grid_alg/terrain.py

from __future__ import annotations
from typing import Any, List
import math

from opensimplex import OpenSimplex

from .features import fbm2d
from ..base.constants import KIND_OBSTACLE, KIND_WATER, KIND_GROUND


# НОВАЯ ВСПОМОГАТЕЛЬНАЯ ФУНКЦИЯ: Применение кривой
def _apply_shaping_curve(grid: List[List[float]], power: float):
    """Применяет степенную функцию к каждому значению высоты."""
    if power == 1.0: return
    for z in range(len(grid)):
        for x in range(len(grid[0])):
            grid[z][x] = math.pow(grid[z][x], power)


# НОВАЯ ВСПОМОГАТЕЛЬНАЯ ФУНКЦИЯ: Сглаживание
def _smooth_grid(grid: List[List[float]], passes: int):
    """Применяет простой фильтр размытия (box blur) для сглаживания."""
    if passes <= 0: return

    h, w = len(grid), len(grid[0])
    for _ in range(passes):
        new_grid = [[0.0] * w for _ in range(h)]
        for z in range(h):
            for x in range(w):
                total, count = 0.0, 0
                # Проходим по соседям 3x3
                for dz in range(-1, 2):
                    for dx in range(-1, 2):
                        nz, nx = z + dz, x + dx
                        if 0 <= nz < h and 0 <= nx < w:
                            total += grid[nz][nx]
                            count += 1
                new_grid[z][x] = total / count
        grid = new_grid  # Обновляем сетку для следующего прохода


# НОВАЯ ВСПОМОГАТЕЛЬНАЯ ФУНКЦИЯ: Квантование
def _quantize_heights(grid: List[List[float]], step: float):
    """Округляет высоты до ближайшего шага для создания террас."""
    if step <= 0: return
    for z in range(len(grid)):
        for x in range(len(grid[0])):
            grid[z][x] = round(grid[z][x] / step) * step


# ОБНОВЛЕННАЯ ГЛАВНАЯ ФУНКЦИЯ
def generate_elevation(seed: int, cx: int, cz: int, size: int, preset: Any) -> List[List[float]]:
    """Создает продвинутую карту высот для всего чанка, используя пресет."""

    # ---> ИЗМЕНЕНИЕ 1: Создаем ЕДИНЫЙ экземпляр OpenSimplex для этого чанка <---
    noise_gen = OpenSimplex(seed)

    cfg = getattr(preset, "elevation", {})
    is_enabled = cfg.get("enabled", False)

    if not is_enabled:
        grid = [[0.0 for _ in range(size)] for _ in range(size)]
        freq = 1.0 / 32.0
        for z in range(size):
            for x in range(size):
                wx, wz = cx * size + x, cz * size + z
                # ---> ИЗМЕНЕНИЕ 2: Передаем noise_gen в fbm2d <---
                grid[z][x] = fbm2d(noise_gen, float(wx), float(wz), freq, octaves=4, gain=0.5)
        return grid

    grid = [[0.0 for _ in range(size)] for _ in range(size)]
    freq = 1.0 / 32.0
    for z in range(size):
        for x in range(size):
            wx, wz = cx * size + x, cz * size + z
            # ---> ИЗМЕНЕНИЕ 2 (повтор): Передаем noise_gen в fbm2d <---
            noise_val = fbm2d(noise_gen, float(wx), float(wz), freq, octaves=4, gain=0.5)
            grid[z][x] = max(0.0, min(1.0, noise_val))

    _apply_shaping_curve(grid, float(cfg.get("shaping_power", 1.0)))

    max_h = float(cfg.get("max_height_m", 50.0))
    for z in range(size):
        for x in range(size):
            grid[z][x] *= max_h

    _smooth_grid(grid, int(cfg.get("smoothing_passes", 0)))
    _quantize_heights(grid, float(cfg.get("quantization_step_m", 0.0)))

    return grid


def classify_terrain(
        elevation_grid: List[List[float]],
        kind_grid: List[List[str]],
        preset: Any
) -> None:
    """Заполняет kind_grid типами ландшафта на основе АБСОЛЮТНЫХ высот из пресета."""
    size = len(kind_grid)

    # --- ИЗМЕНЕНО: Получаем глобальные уровни из пресета ---
    cfg = getattr(preset, "elevation", {})
    # Значения по умолчанию, если в пресете чего-то нет
    sea_level = float(cfg.get("sea_level_m", 20.0))
    mountain_level = float(cfg.get("mountain_level_m", 45.0))

    # --- ИЗМЕНЕНО: Убрана локальная нормализация ---
    for z in range(size):
        for x in range(size):
            elev = elevation_grid[z][x]  # Берем реальную высоту в метрах

            if elev < sea_level:
                kind_grid[z][x] = KIND_WATER
            elif elev > mountain_level:
                kind_grid[z][x] = KIND_OBSTACLE
            else:
                kind_grid[z][x] = KIND_GROUND