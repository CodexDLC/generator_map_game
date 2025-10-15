# generator_logic/climate/local_effects.py
from __future__ import annotations
from typing import Dict, Tuple
import numpy as np
from math import radians, cos, sin
from scipy.ndimage import gaussian_filter

def apply_orographic_effects(
    humidity_grid: np.ndarray,
    height_grid: np.ndarray,
    orographic_cfg: Dict,
    cell_size_m: float
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Моделирует влияние ветра на влажность: орографический подъем и дождевую тень.
    Возвращает обновленную карту влажности и карту "тени".
    """
    # Сглаживаем рельеф для более стабильных градиентов
    sigma = orographic_cfg.get("smoothing_sigma", 1.0)
    smoothed_height = gaussian_filter(height_grid, sigma=sigma, mode='reflect', truncate=3.0)

    # Рассчитываем градиенты (направление и крутизну склонов)
    gz, gx = np.gradient(smoothed_height, cell_size_m)

    # Определяем направление ветра и его проекцию на склоны
    wind_angle_deg = float(orographic_cfg.get("wind_dir_deg", 225.0))
    wdx, wdz = cos(radians(wind_angle_deg)), -sin(radians(wind_angle_deg))
    projection = gx * wdx + gz * wdz

    # Моделируем орографический подъем (увеличение влажности на наветренных склонах)
    lift_scale = orographic_cfg.get("lift_effect_scale", 0.25)
    lift_effect = 1.0 - np.exp(-np.maximum(0.0, projection) / (lift_scale + 1e-9))

    # Моделируем дождевую тень (уменьшение влажности на подветренных склонах)
    shadow_scale = orographic_cfg.get("shadow_effect_scale", 0.25)
    shadow_effect = 1.0 - np.exp(-np.maximum(0.0, -projection) / (shadow_scale + 1e-9))

    # Применяем эффекты
    humidity_grid += lift_effect * orographic_cfg.get("lift_strength", 0.3)
    humidity_grid -= shadow_effect * orographic_cfg.get("shadow_strength", 0.5)

    return np.clip(humidity_grid, 0.0, 1.0), shadow_effect