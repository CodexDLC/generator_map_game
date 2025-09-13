# Файл: game_engine_restructured/algorithms/climate/climate.py
from __future__ import annotations
from typing import TYPE_CHECKING, Dict
import numpy as np
from math import radians, cos, sin
from scipy.ndimage import binary_erosion, gaussian_filter

from ...core.preset.model import Preset
from ...core import constants as const
from .climate_helpers import (
    _derive_seed, _vectorized_smoothstep
)
from ...core.noise.fast_noise import fbm_grid, fbm_amplitude
from ..hydrology.fast_hydrology import _chamfer_distance_transform

if TYPE_CHECKING:
    from ...core.types import GenResult


def generate_climate_maps(
        stitched_layers_ext: Dict[str, np.ndarray],
        preset: Preset,
        world_seed: int,
        base_cx: int,
        base_cz: int,
        region_pixel_size: int,
        scratch_buffers: Dict[str, np.ndarray] # Принимаем буферы
) -> Dict[str, np.ndarray]:

    climate_cfg = preset.climate
    if not climate_cfg.get("enabled"): return {}
    mpp = float(preset.cell_size)
    size = region_pixel_size
    gx0_px = base_cx * preset.size
    gz0_px = base_cz * preset.size
    generated_maps: Dict[str, np.ndarray] = {}
    height_grid_ext = stitched_layers_ext['height']

    temp_cfg = climate_cfg.get("temperature", {})
    if temp_cfg.get("enabled"):
        temperature_grid = np.full((size, size), temp_cfg.get("base_c", 18.0), dtype=np.float32)
        Z_m = (np.arange(size, dtype=np.float32) + gz0_px) * mpp
        temperature_grid += (Z_m[:, np.newaxis] * temp_cfg.get("gradient_c_per_km", -0.02) * 0.001)
        total_noise = np.zeros((size, size), dtype=np.float32)
        noise_layers = temp_cfg.get("noise_layers", {})
        for name, layer_cfg in noise_layers.items():
            scale_m = float(layer_cfg.get("scale_km", 1.0)) * 1000.0
            freq = 1.0 / scale_m if scale_m > 0 else 0
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

    humidity_cfg = climate_cfg.get("humidity", {})
    if humidity_cfg.get("enabled"):
        humidity_base = np.full((size, size), humidity_cfg.get("base", 0.45), dtype=np.float32)
        total_noise_h = np.zeros((size, size), dtype=np.float32)
        noise_layers_h = humidity_cfg.get("noise_layers", {})
        for name, layer_cfg in noise_layers_h.items():
            scale_m = float(layer_cfg.get("scale_km", 1.0)) * 1000.0
            freq = 1.0 / scale_m if scale_m > 0 else 0
            amp = float(layer_cfg.get("amp", 0.0))
            seed = _derive_seed(world_seed, f"climate.humidity.{name}")
            fbm = fbm_grid(seed, gx0_px, gz0_px, size, mpp, freq, 5, 2.0, 0.5, 0.0)
            fbm /= fbm_amplitude(0.5, 5)
            total_noise_h += fbm * amp
        humidity_base += total_noise_h

        T_c = generated_maps["temperature"]
        dry_T0_c = humidity_cfg.get("dry_T0_c", 22.0)
        dry_span_c = humidity_cfg.get("dry_span_c", 15.0)
        Tn = np.clip((T_c - dry_T0_c) / dry_span_c, 0, 1)

        is_water = stitched_layers_ext["navigation"] == const.NAV_WATER
        coast_dist_px = _chamfer_distance_transform(~is_water)
        continentality = np.clip(coast_dist_px / (size / 4), 0, 1)

        sea_level = preset.elevation.get("sea_level_m", 40.0)
        max_h = preset.elevation.get("max_height_m", 150.0)
        orography = np.clip((height_grid_ext - sea_level) / (max_h - sea_level + 1e-6), 0, 1)

        dryness = np.zeros_like(T_c)
        dryness += humidity_cfg.get("w_temp_dry", 0.4) * Tn
        dryness += humidity_cfg.get("w_coast", 0.25) * continentality
        dryness += humidity_cfg.get("w_orography", 0.1) * orography

        river_mask_ext = stitched_layers_ext.get("river", np.zeros_like(height_grid_ext, dtype=bool))
        river_dist_px = _chamfer_distance_transform(~river_mask_ext)
        near_river = 1.0 - np.clip(river_dist_px / 512.0, 0, 1)

        dryness += humidity_cfg.get("w_near_river", -0.3) * near_river

        dryness = np.clip(dryness, 0, 1)
        dry_final = _vectorized_smoothstep(0.35, 0.55, dryness)
        generated_maps["temp_dry"] = dry_final

        humidity_final = humidity_base * (1.0 - 0.5 * dry_final)

        Hs_padded = stitched_layers_ext['height'] # Больше не нужен ручной pad
        gaussian_filter(Hs_padded, sigma=1.0, output=scratch_buffers['a'], mode='reflect', truncate=3.0)
        Hs = scratch_buffers['a']

        gz, gx = np.gradient(Hs, mpp)
        ang = float(humidity_cfg.get("wind_dir_deg", 225.0))
        wdx, wdz = cos(radians(ang)), -sin(radians(ang))
        proj = gx * wdx + gz * wdz
        lift = 1.0 - np.exp(-np.maximum(0.0, proj) / 0.25)
        shadow = 1.0 - np.exp(-np.maximum(0.0, -proj) / 0.25)

        water_core = binary_erosion(is_water, iterations=3)
        coast_dist_for_effect = _chamfer_distance_transform(~water_core)
        coast_exp_term = np.exp(-coast_dist_for_effect * mpp / 250.0)
        gaussian_filter(coast_exp_term, sigma=2.0, output=scratch_buffers['b'], mode='reflect', truncate=3.0)
        coast_term = scratch_buffers['b']

        humidity_final += coast_term * humidity_cfg.get("w_coast", 0.35)
        humidity_final += lift * humidity_cfg.get("w_orography", 0.3)
        humidity_final -= shadow * humidity_cfg.get("w_rain_shadow", 0.25)

        clamp_min_h, clamp_max_h = humidity_cfg.get("clamp", [0.0, 1.0])
        np.clip(humidity_final, clamp_min_h, clamp_max_h, out=humidity_final)
        generated_maps["humidity"] = humidity_final.astype(np.float32)
        generated_maps["coast"] = continentality
        generated_maps["shadow"] = shadow

    print(f"  -> Multi-scale climate maps generated for region.")
    return generated_maps