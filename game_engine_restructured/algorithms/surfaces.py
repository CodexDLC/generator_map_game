# ==============================================================================
# Файл: game_engine_restructured/world/planners/surface_planner.py
# Назначение: "Специалист" по нанесению геологических текстур (земля, песок, скалы).
# ВЕРСИЯ С ОТЛАДКОЙ И ИСПРАВЛЕНИЯМИ
# ==============================================================================
from __future__ import annotations
from typing import Any
import numpy as np

from game_engine_restructured.core import constants as const
from game_engine_restructured.core.constants import surface_fill, surface_set, nav_fill
from game_engine_restructured.numerics.slope import compute_slope_mask


def classify_initial_terrain(surface_grid: np.ndarray, nav_grid: np.ndarray):
    """
    Шаг 1: "Грунтовка". Заливает всю карту базовой текстурой земли и делает ее проходимой.
    """
    print("  -> [Surface] Applying initial terrain classification (dirt/passable)...")
    surface_fill(surface_grid, const.KIND_BASE_DIRT)
    nav_fill(nav_grid, const.NAV_PASSABLE)


def apply_slope_textures(height_grid: np.ndarray, surface_grid: np.ndarray, preset: Any):
    """
    Шаг 2: Наносит текстуру скал (rock) на крутые склоны.
    """
    s_cfg = dict(getattr(preset, "slope_obstacles", {}) or {})
    if not s_cfg.get("enabled", False):
        return

    print("  -> [Surface] Applying slope textures (rock)...")
    angle = float(s_cfg.get("angle_threshold_deg", 45.0))
    band = int(s_cfg.get("band_cells", 3))
    cell = float(getattr(preset, "cell_size", 1.0))

    # Рассчитываем маску крутых склонов
    slope_mask = compute_slope_mask(height_grid, cell, angle, band)

    # --- ОТЛАДОЧНЫЙ ВЫВОД ---
    pixels_changed = np.sum(slope_mask)
    print(f"    -> Found {pixels_changed} steep slope pixels to turn into rock.")

    # Применяем текстуру скал по маске
    if pixels_changed > 0:
        surface_set(surface_grid, slope_mask, const.KIND_BASE_ROCK)


def apply_beach_sand(height_grid: np.ndarray, surface_grid: np.ndarray, preset: Any):
    """
    Шаг 3: Наносит текстуру песка (sand) на пляжи.
    """
    # --- ИСПРАВЛЕНИЕ БАГА: Читаем настройки из пресета, а не используем "магические числа" ---
    beach_cfg = dict(getattr(preset, "surfaces", {}).get("beach", {}))
    if not beach_cfg.get("enabled", False):
        return

    sea_level = float(getattr(preset, "elevation", {}).get("sea_level_m", 40.0))
    beach_height = float(beach_cfg.get("height_above_sea_m", 3.0))
    beach_upper_limit = sea_level + beach_height

    print(f"  -> [Surface] Applying beach textures (sand) up to {beach_upper_limit:.1f}m...")

    # Находим участки, которые:
    # 1. Не являются водой (уже установленной на предыдущем шаге)
    # 2. Находятся в пределах высоты пляжа
    # 3. Еще не являются скалами (у скал приоритет выше)
    is_land = surface_grid != const.SURFACE_KIND_TO_ID[const.KIND_BASE_WATERBED]
    is_low_enough = height_grid < beach_upper_limit
    is_not_rock = surface_grid != const.SURFACE_KIND_TO_ID[const.KIND_BASE_ROCK]

    beach_mask = is_land & is_low_enough & is_not_rock

    # --- ОТЛАДОЧНЫЙ ВЫВОД ---
    pixels_changed = np.sum(beach_mask)
    print(f"    -> Found {pixels_changed} beach pixels to turn into sand.")

    # Применяем текстуру песка
    if pixels_changed > 0:
        surface_set(surface_grid, beach_mask, const.KIND_BASE_SAND)