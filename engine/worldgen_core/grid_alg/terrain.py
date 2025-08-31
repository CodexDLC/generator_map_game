# engine/worldgen_core/grid_alg/terrain.py
from __future__ import annotations
from typing import Any, List
import math

from opensimplex import OpenSimplex

from .features import fbm2d
from ..base.constants import KIND_OBSTACLE, KIND_WATER, KIND_GROUND


# --- Вспомогательные функции (без изменений) ---

def _apply_shaping_curve(grid: List[List[float]], power: float):
    if power == 1.0: return
    for z in range(len(grid)):
        for x in range(len(grid[0])):
            grid[z][x] = math.pow(grid[z][x], power)


def _smooth_grid(grid: List[List[float]], passes: int):
    if passes <= 0: return grid  # <<< ИЗМЕНЕНИЕ: Возвращаем grid, если нет изменений

    h, w = len(grid), len(grid[0])
    # Создаем копию для работы, чтобы не изменять исходный grid во время итерации
    temp_grid = [row[:] for row in grid]

    for _ in range(passes):
        new_grid = [row[:] for row in temp_grid]
        for z in range(h):
            for x in range(w):
                # Пропускаем края, чтобы избежать артефактов на границах увеличенной сетки
                if x == 0 or x == w - 1 or z == 0 or z == h - 1:
                    continue

                total, count = 0.0, 0
                for dz in range(-1, 2):
                    for dx in range(-1, 2):
                        total += temp_grid[z + dz][x + dx]
                        count += 1
                new_grid[z][x] = total / count
        temp_grid = new_grid

    return temp_grid


def _quantize_heights(grid: List[List[float]], step: float):
    if step <= 0: return
    for z in range(len(grid)):
        for x in range(len(grid[0])):
            grid[z][x] = round(grid[z][x] / step) * step


# <<< НОВАЯ ВСПОМОГАТЕЛЬНАЯ ФУНКЦИЯ >>>
def _crop_grid(grid: List[List[float]], target_size: int, margin: int) -> List[List[float]]:
    """Обрезает увеличенную сетку до целевого размера, убирая 'нахлест'."""
    cropped = [[0.0] * target_size for _ in range(target_size)]
    for z in range(target_size):
        for x in range(target_size):
            cropped[z][x] = grid[z + margin][x + margin]
    return cropped


# <<< КЛЮЧЕВЫЕ ИЗМЕНЕНИЯ ЗДЕСЬ >>>
def generate_elevation(seed: int, cx: int, cz: int, size: int, preset: Any) -> List[List[float]]:
    """
    Создает бесшовную карту высот, генерируя область с 'нахлестом' (margin),
    применяя к ней эффекты и затем обрезая до нужного размера.
    """
    noise_gen = OpenSimplex(seed)
    cfg = getattr(preset, "elevation", {})

    # Определяем 'нахлест'. 2 пикселя - хороший баланс между качеством и скоростью.
    margin = 2
    working_size = size + margin * 2

    # Мировые координаты левого-верхнего угла увеличенной сетки
    base_wx = cx * size - margin
    base_wz = cz * size - margin

    # ШАГ 1: Генерируем увеличенную карту высот
    large_grid = [[0.0 for _ in range(working_size)] for _ in range(working_size)]
    freq = 1.0 / 32.0
    for z in range(working_size):
        for x in range(working_size):
            # Считаем мировые координаты для каждой точки увеличенной сетки
            wx, wz = base_wx + x, base_wz + z
            noise_val = fbm2d(noise_gen, float(wx), float(wz), freq, octaves=4, gain=0.5)
            large_grid[z][x] = max(0.0, min(1.0, noise_val))

    # ШАГ 2: Применяем все эффекты к этой БОЛЬШОЙ карте
    _apply_shaping_curve(large_grid, float(cfg.get("shaping_power", 1.0)))

    max_h = float(cfg.get("max_height_m", 50.0))
    for z in range(working_size):
        for x in range(working_size):
            large_grid[z][x] *= max_h

    # Сглаживание теперь работает на большой сетке, что убирает швы
    smoothed_grid = _smooth_grid(large_grid, int(cfg.get("smoothing_passes", 0)))
    _quantize_heights(smoothed_grid, float(cfg.get("quantization_step_m", 0.0)))

    # ШАГ 3: Обрезаем результат до оригинального размера чанка
    final_grid = _crop_grid(smoothed_grid, size, margin)

    return final_grid


def classify_terrain(
        elevation_grid: List[List[float]],
        kind_grid: List[List[str]],
        preset: Any
) -> None:
    """Заполняет kind_grid типами ландшафта. Работает уже с финальной, обрезанной сеткой."""
    size = len(kind_grid)
    cfg = getattr(preset, "elevation", {})
    sea_level = float(cfg.get("sea_level_m", 20.0))
    mountain_level = float(cfg.get("mountain_level_m", 45.0))

    for z in range(size):
        for x in range(size):
            elev = elevation_grid[z][x]

            if elev < sea_level:
                kind_grid[z][x] = KIND_WATER
            elif elev > mountain_level:
                kind_grid[z][x] = KIND_OBSTACLE
            else:
                kind_grid[z][x] = KIND_GROUND