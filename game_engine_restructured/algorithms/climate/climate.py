# ==============================================================================
# Файл: game_engine_restructured/algorithms/climate/climate.py
# ВЕРСИЯ 2.0: Код отрефакторен согласно вашим рекомендациям.
# ==============================================================================
from __future__ import annotations
import logging  # ИЗМЕНЕНИЕ: Импортируем модуль логирования
import time

from typing import TYPE_CHECKING, Dict, Tuple
import numpy as np
from math import radians, cos, sin
from scipy.ndimage import binary_erosion, gaussian_filter

from ...core.preset.model import Preset
from ...core import constants as const
from .climate_helpers import (
    _derive_seed, _vectorized_smoothstep
)
from game_engine_restructured.numerics.fast_noise_2d import fbm_grid_bipolar as fbm_grid # Даем псевдоним
from game_engine_restructured.numerics.fast_noise_helpers import fbm_amplitude
from game_engine_restructured.numerics.fast_hydrology import chamfer_distance_transform

if TYPE_CHECKING:
    pass

# ИЗМЕНЕНИЕ: Настраиваем базовый логгер для модуля
logger = logging.getLogger(__name__)
if not logger.handlers:
    logging.basicConfig(level=logging.INFO, format='  -> [%(levelname)s] %(message)s')


# ==============================================================================
# --- Вспомогательные под-функции для расчета влажности ---
# ==============================================================================

def _calculate_dryness(
        humidity_cfg: Dict,
        temperature_grid: np.ndarray,
        height_grid_ext: np.ndarray,
        is_water_mask: np.ndarray,
        river_mask_ext: np.ndarray,
        sea_level_m: float,
        max_height_m: float
) -> np.ndarray:
    """
    Рассчитывает базовый уровень "сухости" на основе температуры,
    удаленности от побережья, высоты и близости к рекам.
    """
    # Влияние температуры на сухость
    dry_t0 = humidity_cfg.get("dry_T0_c", 22.0)
    dry_span = humidity_cfg.get("dry_span_c", 15.0)
    temp_norm = np.clip((temperature_grid - dry_t0) / dry_span, 0, 1)

    # Влияние удаленности от крупных водоемов (континентальность)
    coast_dist_px = chamfer_distance_transform(~is_water_mask)
    continentality = np.clip(coast_dist_px / (temperature_grid.shape[0] / 4), 0, 1)

    # Влияние высоты над уровнем моря
    orography = np.clip((height_grid_ext - sea_level_m) / (max_height_m - sea_level_m + 1e-6), 0, 1)

    # Влияние близости к рекам (увлажнение)
    river_dist_px = chamfer_distance_transform(~river_mask_ext)
    river_proximity_threshold = humidity_cfg.get("river_proximity_threshold_px", 512.0)
    near_river = 1.0 - np.clip(river_dist_px / river_proximity_threshold, 0, 1)

    # Суммируем все факторы с весами из пресета
    dryness = (
            humidity_cfg.get("w_temp_dry", 0.4) * temp_norm +
            humidity_cfg.get("w_coast", 0.25) * continentality +
            humidity_cfg.get("w_orography", 0.1) * orography +
            humidity_cfg.get("w_near_river", -0.3) * near_river
    )
    dryness_clipped = np.clip(dryness, 0, 1)

    # Применяем плавный переход для итоговой маски сухости
    return _vectorized_smoothstep(0.35, 0.55, dryness_clipped)


def _apply_orographic_effects(
        humidity_grid: np.ndarray,
        height_grid_ext: np.ndarray,
        is_water_mask: np.ndarray,
        humidity_cfg: Dict,
        mpp: float,
        scratch_buffer_a: np.ndarray,
        scratch_buffer_b: np.ndarray
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Моделирует влияние ветра на влажность: орографический подъем и дождевую тень.
    """
    # Сглаживаем рельеф для более стабильных градиентов
    sigma = humidity_cfg.get("orographic_smoothing_sigma", 1.0)
    gaussian_filter(height_grid_ext, sigma=sigma, output=scratch_buffer_a, mode='reflect', truncate=3.0)

    # Рассчитываем градиенты (направление и крутизну склонов)
    gz, gx = np.gradient(scratch_buffer_a, mpp)

    # Определяем направление ветра и его проекцию на склоны
    wind_angle_deg = float(humidity_cfg.get("wind_dir_deg", 225.0))
    wdx, wdz = cos(radians(wind_angle_deg)), -sin(radians(wind_angle_deg))
    projection = gx * wdx + gz * wdz

    # Моделируем орографический подъем (увеличение влажности на наветренных склонах)
    lift_scale = humidity_cfg.get("lift_effect_scale", 0.25)
    lift_effect = 1.0 - np.exp(-np.maximum(0.0, projection) / lift_scale)

    # Моделируем дождевую тень (уменьшение влажности на подветренных склонах)
    shadow_scale = humidity_cfg.get("shadow_effect_scale", 0.25)
    shadow_effect = 1.0 - np.exp(-np.maximum(0.0, -projection) / shadow_scale)

    # Моделируем повышенную влажность у побережья
    erosion_iter = humidity_cfg.get("coast_erosion_iterations", 3)
    coast_core = binary_erosion(is_water_mask, iterations=erosion_iter)
    coast_dist = chamfer_distance_transform(~coast_core)
    coast_falloff_m = humidity_cfg.get("coast_effect_falloff_m", 250.0)
    coast_exp_term = np.exp(-coast_dist * mpp / coast_falloff_m)
    gaussian_filter(coast_exp_term, sigma=2.0, output=scratch_buffer_b, mode='reflect', truncate=3.0)
    coast_term = scratch_buffer_b

    # Применяем все эффекты с весами из пресета
    humidity_grid += coast_term * humidity_cfg.get("w_coast", 0.35)
    humidity_grid += lift_effect * humidity_cfg.get("w_orography", 0.3)
    humidity_grid -= shadow_effect * humidity_cfg.get("w_rain_shadow", 0.25)

    return humidity_grid, shadow_effect


# ==============================================================================
# --- Основная функция генерации ---
# ==============================================================================

def generate_climate_maps(
        stitched_layers_ext: Dict[str, np.ndarray],
        preset: Preset,
        world_seed: int,
        scx: int,  # scx, scz - координаты региона
        scz: int,
        region_pixel_size: int,
        scratch_buffers: Dict[str, np.ndarray]
) -> Dict[str, np.ndarray]:
    """
    Генерирует климатические карты (температуры, влажности и др.) для заданного региона.

    Args:
        stitched_layers_ext (Dict[str, np.ndarray]): Словарь с входными слоями (высота, навигация, реки).
        preset (Preset): Объект конфигурации с параметрами климата.
        world_seed (int): Основной сид для генерации шума.
        scx (int): Координата X региона.
        scz (int): Координата Z региона.
        region_pixel_size (int): Размер региона в пикселях.
        scratch_buffers (Dict[str, np.ndarray]): Пре-аллоцированные буферы для временных расчетов.

    Returns:
        Dict[str, np.ndarray]: Словарь, содержащий сгенерированные климатические карты.
    """
    # --- Блок 0: Проверка и подготовка ---
    climate_cfg = preset.climate
    if not climate_cfg.get("enabled"):
        return {}

    # ИЗМЕНЕНИЕ: Проверяем наличие обязательных входных данных
    required_layers = ['height', 'navigation']
    for layer in required_layers:
        if layer not in stitched_layers_ext:
            raise ValueError(f"Слой '{layer}' обязателен для генерации климата.")

    mpp = float(preset.cell_size)
    size = region_pixel_size
    base_cx = scx * preset.region_size
    base_cz = scz * preset.region_size
    gx0_px = base_cx * preset.size
    gz0_px = base_cz * preset.size
    generated_maps: Dict[str, np.ndarray] = {}
    height_grid_ext = stitched_layers_ext['height']

    # --- Блок 1: Генерация температуры ---
    temp_cfg = climate_cfg.get("temperature", {})
    if temp_cfg.get("enabled"):
        t_start = time.perf_counter()
        temperature_grid = np.full((size, size), temp_cfg.get("base_c", 18.0), dtype=np.float32)
        Z_m = (np.arange(size, dtype=np.float32) + gz0_px) * mpp
        temperature_grid += (Z_m[:, np.newaxis] * temp_cfg.get("gradient_c_per_km", -0.02) * 0.001)

        total_noise = np.zeros((size, size), dtype=np.float32)
        for name, layer_cfg in temp_cfg.get("noise_layers", {}).items():
            freq = 1.0 / (float(layer_cfg.get("scale_km", 1.0)) * 1000.0)
            amp = float(layer_cfg.get("amp_c", 0.0))
            seed = _derive_seed(world_seed, f"climate.temperature.{name}")
            fbm = fbm_grid(seed, gx0_px, gz0_px, size, mpp, freq, 5, 2.0, 0.5, 0.0)
            fbm /= fbm_amplitude(0.5, 5)
            total_noise += fbm * amp

        temperature_grid += total_noise
        temperature_grid += height_grid_ext * temp_cfg.get("lapse_rate_c_per_m", -0.0065)

        clamp_min, clamp_max = temp_cfg.get("clamp_c", [-25.0, 40.0])
        np.clip(temperature_grid, clamp_min, clamp_max, out=temperature_grid)
        generated_maps["temperature"] = temperature_grid
        logger.info(f"Карта температур сгенерирована за {(time.perf_counter() - t_start) * 1000:.1f} мс.")

    # --- Блок 2: Генерация влажности ---
    humidity_cfg = climate_cfg.get("humidity", {})
    if humidity_cfg.get("enabled"):
        h_start = time.perf_counter()
        humidity_base = np.full((size, size), humidity_cfg.get("base", 0.45), dtype=np.float32)

        total_noise_h = np.zeros((size, size), dtype=np.float32)
        for name, layer_cfg in humidity_cfg.get("noise_layers", {}).items():
            freq = 1.0 / (float(layer_cfg.get("scale_km", 1.0)) * 1000.0)
            amp = float(layer_cfg.get("amp", 0.0))
            seed = _derive_seed(world_seed, f"climate.humidity.{name}")
            fbm = fbm_grid(seed, gx0_px, gz0_px, size, mpp, freq, 5, 2.0, 0.5, 0.0)
            fbm /= fbm_amplitude(0.5, 5)
            total_noise_h += fbm * amp
        humidity_base += total_noise_h

        # --- ИЗМЕНЕНИЕ: Используем разделенные функции ---
        is_water = stitched_layers_ext["navigation"] == const.NAV_WATER
        river_mask_ext = stitched_layers_ext.get("river", np.zeros_like(height_grid_ext, dtype=bool))
        sea_level = preset.elevation.get("sea_level_m", 40.0)
        max_h = preset.elevation.get("max_height_m", 150.0)

        dry_final = _calculate_dryness(
            humidity_cfg, generated_maps["temperature"], height_grid_ext, is_water, river_mask_ext, sea_level, max_h
        )
        generated_maps["temp_dry"] = dry_final

        humidity_final = humidity_base * (1.0 - 0.5 * dry_final)

        humidity_final, shadow_map = _apply_orographic_effects(
            humidity_final, height_grid_ext, is_water, humidity_cfg, mpp,
            scratch_buffers['a'], scratch_buffers['b']
        )

        clamp_min_h, clamp_max_h = humidity_cfg.get("clamp", [0.0, 1.0])
        np.clip(humidity_final, clamp_min_h, clamp_max_h, out=humidity_final)

        generated_maps["humidity"] = humidity_final.astype(np.float32)
        generated_maps["coast"] = chamfer_distance_transform(~is_water)  # Re-using for analytics
        generated_maps["shadow"] = shadow_map
        logger.info(f"Карта влажности сгенерирована за {(time.perf_counter() - h_start) * 1000:.1f} мс.")

    return generated_maps