# generator_logic/climate/climate_model.py
from __future__ import annotations
from typing import Dict, Tuple
import numpy as np
from math import radians, cos, sin
from scipy.ndimage import binary_erosion, gaussian_filter
from game_engine_restructured.numerics.fast_hydrology import chamfer_distance_transform

# ==============================================================================
# --- Вспомогательные под-функции, перенесенные и адаптированные ---
# ==============================================================================

def _vectorized_smoothstep(edge0: float, edge1: float, x_array: np.ndarray) -> np.ndarray:
    """GLSL-like smoothstep, numba-compatible."""
    inv_span = 1.0 / (edge1 - edge0 + 1e-9)
    t = (x_array - edge0) * inv_span
    t = np.clip(t, 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)

# ==============================================================================
# --- Этап 2: Реализация модели влажности ---
# ==============================================================================

def _calculate_base_humidity(
    is_water_mask: np.ndarray,
    river_mask: np.ndarray,
    params: dict,
    mpp: float # meters per pixel
) -> np.ndarray:
    """
    Расчет базовой влажности на основе близости к океанам и рекам.
    """
    # 1. Расстояние до крупных водоемов (океаны/моря)
    coast_dist_px = chamfer_distance_transform(~is_water_mask)
    coast_falloff_m = params.get("coast_effect_falloff_m", 50000.0)
    # Влажность спадает экспоненциально от побережья
    coastal_humidity = np.exp(-coast_dist_px * mpp / coast_falloff_m)

    # 2. Расстояние до рек
    river_dist_px = chamfer_distance_transform(~river_mask)
    river_proximity_threshold_px = params.get("river_proximity_threshold_px", 128.0)
    # Влажность повышена вблизи рек
    river_humidity = 1.0 - np.clip(river_dist_px / river_proximity_threshold_px, 0.0, 1.0)
    river_humidity = _vectorized_smoothstep(0.0, 1.0, river_humidity)

    # 3. Комбинирование с весами
    base_humidity = (
        coastal_humidity * params.get("w_coast_humidity", 0.7) +
        river_humidity * params.get("w_river_humidity", 0.3)
    )
    return np.clip(base_humidity, 0.0, 1.0)


def _apply_temperature_to_humidity(
    humidity_map: np.ndarray,
    temperature_map: np.ndarray,
    params: dict
) -> np.ndarray:
    """
    Корректирует влажность, создавая засушливые зоны в жарких регионах.
    """
    dry_t0 = params.get("dry_T0_c", 25.0)
    dry_span = params.get("dry_span_c", 15.0)

    # "Маска сухости": 0 где холодно, 1 где очень жарко
    dryness_factor = (temperature_map - dry_t0) / dry_span
    dryness_mask = _vectorized_smoothstep(0.0, 1.0, dryness_factor)

    # Уменьшаем влажность в засушливых зонах
    w_temp_dry = params.get("w_temp_dry", 0.8)
    updated_humidity = humidity_map * (1.0 - dryness_mask * w_temp_dry)
    return np.clip(updated_humidity, 0.0, 1.0)

# ==============================================================================
# --- Этап 3: Реализация модели ветров и орографии ---
# ==============================================================================

def apply_orographic_effects(
    humidity_map: np.ndarray,
    height_map: np.ndarray,
    cell_size_m: float,
    params: dict
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Моделирует влияние ветра на влажность: орографический подъем и дождевую тень.
    """
    # Сглаживаем рельеф для более стабильных градиентов
    sigma = params.get("orographic_smoothing_sigma", 2.0)
    smoothed_height = gaussian_filter(height_map, sigma=sigma, mode='reflect', truncate=3.0)

    # Рассчитываем градиенты
    gz, gx = np.gradient(smoothed_height, cell_size_m)

    # Определяем направление ветра и его проекцию на склоны
    wind_angle_deg = float(params.get("wind_dir_deg", 225.0))
    wdx, wdz = cos(radians(wind_angle_deg)), -sin(radians(wind_angle_deg))
    projection = gx * wdx + gz * wdz

    # Орографический подъем (увеличение влажности на наветренных склонах)
    lift_scale = params.get("lift_effect_scale", 100.0)
    lift_effect = 1.0 - np.exp(-np.maximum(0.0, projection) / (lift_scale + 1e-9))

    # Дождевая тень (уменьшение влажности на подветренных склонах)
    shadow_scale = params.get("shadow_effect_scale", 200.0)
    shadow_effect = 1.0 - np.exp(-np.maximum(0.0, -projection) / (shadow_scale + 1e-9))

    # Применяем эффекты с силой из UI
    humidity_map += lift_effect * params.get("lift_strength", 0.4)
    humidity_map -= shadow_effect * params.get("shadow_strength", 0.6)

    return np.clip(humidity_map, 0.0, 1.0), shadow_effect

# ==============================================================================
# --- Этап 4: Финальная сборка ---
# ==============================================================================

def generate_climate_maps(context: dict) -> Dict[str, np.ndarray]:
    """
    Главная функция-оркестратор для генерации климата.
    """
    # 1. Извлекаем необходимые данные из контекста
    params = context.get("climate_params", {})
    if not params.get("enabled", False):
        return {}

    height_map = context["height_map"]
    is_water_mask = context["is_water_mask"]
    river_mask = context["river_mask"]
    temperature_map = context["temperature_map"]
    cell_size_m = context["cell_size_m"]

    # 2. Рассчитываем базовую влажность от воды
    humidity_map = _calculate_base_humidity(is_water_mask, river_mask, params, cell_size_m)

    # 3. Корректируем по температуре
    humidity_map = _apply_temperature_to_humidity(humidity_map, temperature_map, params)

    # 4. Применяем орографические эффекты (ветер и горы)
    humidity_map, rain_shadow_map = apply_orographic_effects(humidity_map, height_map, cell_size_m, params)

    # 5. Возвращаем итоговые карты
    return {
        'humidity': np.clip(humidity_map, 0.0, 1.0).astype(np.float32),
        'rain_shadow': rain_shadow_map.astype(np.float32)
    }