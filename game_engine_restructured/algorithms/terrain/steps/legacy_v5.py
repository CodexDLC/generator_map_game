# Файл: game_engine_restructured/algorithms/terrain/steps/legacy_v5.py
# ЭТОТ ФАЙЛ СОДЕРЖИТ СТАРУЮ ЛОГИКУ ИЗ V5 И НЕ ИСПОЛЬЗУЕТСЯ
# В НОВОМ ДИНАМИЧЕСКОМ КОНВЕЙЕРЕ. ОН СОХРАНЕН ДЛЯ АРХИВА.
from __future__ import annotations

from typing import Any, Dict
import numpy as np

from game_engine_restructured.numerics.fast_noise import fbm_grid_warped, fbm_amplitude, fbm_grid_warped_bipolar


def generate_base_noise(
        seed: int, layer_cfg: Dict, coords_x: np.ndarray, coords_z: np.ndarray, cell_size: float
) -> np.ndarray:
    """Шаг 1: Генерирует сырой, а затем НОРМАЛИЗОВАННЫЙ FBM шум с варпингом."""
    octaves = int(layer_cfg.get("octaves", 4))
    is_ridge = bool(layer_cfg.get("ridge", False))
    scale = float(layer_cfg.get("scale_tiles", 1000)) * cell_size
    freq = 1.0 / scale if scale > 0 else 0.0

    warp_params = {}
    warp_cfg = layer_cfg.get("warp")
    if warp_cfg:
        warp_scale = float(warp_cfg.get("scale_tiles", 1000)) * cell_size
        warp_params = {
            "warp_seed": seed + 7,
            "warp_amp": float(warp_cfg.get("amp", 0.0)),
            "warp_octaves": int(warp_cfg.get("octaves", 2)),
            "warp_freq": 1.0 / warp_scale if warp_scale > 0 else 0.0,
        }

    raw_noise = fbm_grid_warped(
        seed=seed, coords_x=coords_x, coords_z=coords_z, freq0=freq,
        octaves=octaves, ridge=is_ridge, **warp_params
    )

    gain = 0.5
    max_amp = fbm_amplitude(gain, octaves)

    if max_amp > 1e-6:
        normalized_noise = raw_noise / max_amp
    else:
        normalized_noise = raw_noise

    return normalized_noise

def normalize_and_shape(noise: np.ndarray, layer_cfg: Dict) -> np.ndarray:
    noise_normalized = noise.astype(np.float32, copy=False)

    is_base  = bool(layer_cfg.get("is_base", False))
    is_ridge = bool(layer_cfg.get("ridge", False))
    is_add   = bool(layer_cfg.get("additive_only", False))
    power    = float(layer_cfg.get("shaping_power", 1.0))

    if is_base and not is_ridge:
        noise_normalized = (noise_normalized + 1.0) * 0.5

    if is_ridge or is_add:
        np.maximum(0.0, noise_normalized, out=noise_normalized)
        if power != 1.0:
            np.power(noise_normalized, power, out=noise_normalized)

        floor = float(layer_cfg.get("positive_floor", 0.0))
        if floor > 0.0:
            noise_normalized = floor + (1.0 - floor) * noise_normalized
    else:
        if power != 1.0:
            np.power(np.maximum(0.0, noise_normalized), power, out=noise_normalized)
        noise_normalized = (noise_normalized * 2.0) - 1.0

    return noise_normalized

def scale_by_amplitude(noise: np.ndarray, layer_cfg: Dict) -> np.ndarray:
    """Умножает нормализованный шум на его амплитуду в метрах."""
    amp = float(layer_cfg.get("amp_m", 0.0))
    return noise * amp

# --- Главная функция-инструмент для V5 ---
def generate_noise_layer(
        layer_seed: int,
        layer_cfg: Dict[str, Any],
        x_coords: np.ndarray,
        z_coords: np.ndarray,
        cell_size: float
) -> np.ndarray:
    is_additive = bool(layer_cfg.get("additive_only", True))
    warp_cfg = layer_cfg.get("warp", {})
    gain = float(layer_cfg.get("gain", 0.5))
    octaves = int(layer_cfg.get("octaves", 4))

    noise_params = {
        "seed": layer_seed, "coords_x": x_coords, "coords_z": z_coords,
        "freq0": 1.0 / (layer_cfg.get("scale_tiles", 1000.0) * cell_size + 1e-6),
        "octaves": octaves, "ridge": bool(layer_cfg.get("ridge", False)),
        "gain": gain, "lacunarity": float(layer_cfg.get("lacunarity", 2.0)),
        "warp_seed": layer_seed + 54321,
        "warp_amp": float(warp_cfg.get("amp", 0.0)),
        "warp_freq": 1.0 / (warp_cfg.get("scale_tiles", 1000.0) * cell_size + 1e-6),
        "warp_octaves": int(warp_cfg.get("octaves", 2))
    }

    raw_unnormalized_noise = fbm_grid_warped_bipolar(**noise_params)

    max_amp = fbm_amplitude(gain, octaves)
    if max_amp > 1e-6:
        normalized_noise = raw_unnormalized_noise / max_amp
    else:
        normalized_noise = raw_unnormalized_noise

    if is_additive:
        noise_for_shaping = (normalized_noise + 1.0) * 0.5
    else:
        noise_for_shaping = np.abs(normalized_noise)

    shaping_power = float(layer_cfg.get("shaping_power", 1.0))
    if shaping_power != 1.0:
        shaped_noise = np.power(noise_for_shaping, shaping_power)
    else:
        shaped_noise = noise_for_shaping

    if not is_additive:
        final_normalized_noise = np.sign(normalized_noise) * shaped_noise
    else:
        final_normalized_noise = shaped_noise

    final_noise = final_normalized_noise * float(layer_cfg.get("amp_m", 0.0))
    return final_noise