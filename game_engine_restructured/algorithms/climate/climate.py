# Файл: game_engine_restructured/algorithms/climate/climate.py
from __future__ import annotations
from typing import TYPE_CHECKING, Dict
import numpy as np
from math import radians, cos, sin
from scipy.ndimage import binary_erosion

from ...core.preset.model import Preset
from ...core import constants as const
from .climate_helpers import (
    _derive_seed, _fbm_amplitude, _fbm_grid,
    _edt_with_halo, _gauss_with_halo
)

if TYPE_CHECKING:
    from ...core.types import GenResult


def apply_climate_to_surface(chunk: "GenResult"):
    # (Эта функция остается без изменений)
    pass


def generate_climate_maps(
        stitched_layers: Dict[str, np.ndarray],
        preset: Preset,
        world_seed: int,
        base_cx: int,
        base_cz: int,
        region_pixel_size: int
) -> Dict[str, np.ndarray]:
    """
    Генерирует все климатические карты для региона, используя многошкальный шум.
    """
    climate_cfg = preset.climate
    if not climate_cfg.get("enabled"): return {}

    mpp = float(preset.cell_size)
    size = region_pixel_size
    gx0_px = base_cx * preset.size
    gz0_px = base_cz * preset.size

    generated_maps = {}

    # --- 1. Генерация температуры (многошкальный шум) ---
    temp_cfg = climate_cfg.get("temperature", {})
    if temp_cfg.get("enabled"):
        # --- НАЧАЛО ИСПРАВЛЕНИЯ ---
        # Создаем базовый 2D-массив
        temperature_grid = np.full((size, size), temp_cfg.get("base_c", 18.0), dtype=np.float32)
        # Применяем широтный градиент к 2D-массиву
        Z_m = (np.arange(size, dtype=np.float32) + gz0_px) * mpp
        temperature_grid += (Z_m[:, np.newaxis] * temp_cfg.get("gradient_c_per_km", -0.02) * 0.001)
        # --- КОНЕЦ ИСПРАВЛЕНИЯ ---

        total_noise = np.zeros((size, size), dtype=np.float32)
        noise_layers = temp_cfg.get("noise_layers", {})

        for name, layer_cfg in noise_layers.items():
            scale_m = float(layer_cfg.get("scale_km", 1.0)) * 1000.0
            freq = 1.0 / scale_m if scale_m > 0 else 0
            amp = float(layer_cfg.get("amp_c", 0.0))

            seed = _derive_seed(world_seed, f"climate.temperature.{name}")
            fbm = _fbm_grid(seed, gx0_px, gz0_px, size, mpp, freq, 5, 2.0, 0.5, 0.0)
            fbm /= _fbm_amplitude(0.5, 5)
            total_noise += fbm * amp

        temperature_grid += total_noise
        temperature_grid += stitched_layers['height'] * temp_cfg.get("lapse_rate_c_per_m", -0.0065)

        clamp_min, clamp_max = temp_cfg.get("clamp_c", [-25.0, 40.0])
        np.clip(temperature_grid, clamp_min, clamp_max, out=temperature_grid)
        generated_maps["temperature"] = temperature_grid

    # --- 2. Генерация влажности (многошкальный шум + эффекты) ---
    humidity_cfg = climate_cfg.get("humidity", {})
    if humidity_cfg.get("enabled"):
        humidity_grid = np.full((size, size), humidity_cfg.get("base", 0.45), dtype=np.float32)

        total_noise_h = np.zeros((size, size), dtype=np.float32)
        noise_layers_h = humidity_cfg.get("noise_layers", {})
        for name, layer_cfg in noise_layers_h.items():
            scale_m = float(layer_cfg.get("scale_km", 1.0)) * 1000.0
            freq = 1.0 / scale_m if scale_m > 0 else 0
            amp = float(layer_cfg.get("amp", 0.0))
            seed = _derive_seed(world_seed, f"climate.humidity.{name}")
            fbm = _fbm_grid(seed, gx0_px, gz0_px, size, mpp, freq, 5, 2.0, 0.5, 0.0)
            fbm /= _fbm_amplitude(0.5, 5)
            total_noise_h += fbm * amp
        humidity_grid += total_noise_h

        is_water = (stitched_layers["navigation"] == const.NAV_WATER)
        water_core = binary_erosion(is_water, iterations=3)
        coast_term = _gauss_with_halo(np.exp(-_edt_with_halo(water_core, 16, mpp) / 250.0), sigma=2.0, pad=16)
        generated_maps["coast"] = coast_term

        Hs = _gauss_with_halo(stitched_layers["height"], sigma=1.0, pad=16)
        gz, gx = np.gradient(Hs, mpp)
        ang = float(humidity_cfg.get("wind_dir_deg", 225.0))
        wdx, wdz = cos(radians(ang)), -sin(radians(ang))
        proj = gx * wdx + gz * wdz
        lift = 1.0 - np.exp(-np.maximum(0.0, proj) / 0.25)
        shadow = 1.0 - np.exp(-np.maximum(0.0, -proj) / 0.25)
        generated_maps["shadow"] = shadow

        T = generated_maps.get("temperature", np.full_like(is_water, 18.0, dtype=np.float32))
        T0 = float(humidity_cfg.get("dry_T0_c", 22.0))
        Tspan = float(humidity_cfg.get("dry_span_c", 15.0))
        temp_dry = np.clip((T - T0) / Tspan, 0.0, 1.0)
        generated_maps["temp_dry"] = temp_dry

        humidity_grid += coast_term * humidity_cfg.get("w_coast", 0.35)
        humidity_grid += lift * humidity_cfg.get("w_orography", 0.3)
        humidity_grid -= shadow * humidity_cfg.get("w_rain_shadow", 0.25)
        humidity_grid -= temp_dry * humidity_cfg.get("w_temp_dry", 0.4)

        clamp_min_h, clamp_max_h = humidity_cfg.get("clamp", [0.0, 1.0])
        np.clip(humidity_grid, clamp_min_h, clamp_max_h, out=humidity_grid)
        generated_maps["humidity"] = humidity_grid.astype(np.float32)

    generated_maps["river"] = np.zeros((size, size), dtype=np.float32)  # Заглушка для отчета

    print(f"  -> Multi-scale climate maps generated for region.")
    return generated_maps