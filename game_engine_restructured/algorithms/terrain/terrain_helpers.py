# Файл: game_engine_restructured/algorithms/terrain/terrain_helpers.py
from __future__ import annotations
from typing import Any, Dict
import numpy as np

# Импортируем "математику" из numerics и core
from ...numerics.fast_noise import fbm_grid_warped, fbm_amplitude


def generate_base_noise(
        seed: int, layer_cfg: Dict, coords_x: np.ndarray, coords_z: np.ndarray, cell_size: float
) -> np.ndarray:
    """Шаг 1: Генерирует сырой FBM шум с варпингом."""
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

    return fbm_grid_warped(
        seed=seed, coords_x=coords_x, coords_z=coords_z, freq0=freq,
        octaves=octaves, ridge=is_ridge, **warp_params
    )


def normalize_and_shape(noise: np.ndarray, layer_cfg: Dict) -> np.ndarray:
    """Шаг 2: Нормализует, применяет shaping_power и устанавливает диапазон [0,1] или [-1,1]."""
    octaves = int(layer_cfg.get("octaves", 4))
    norm_factor = max(fbm_amplitude(0.5, octaves), 1e-6)
    noise_normalized = noise / norm_factor

    if layer_cfg.get("is_base", False) and not layer_cfg.get("ridge", False):
        noise_normalized = (noise_normalized + 1.0) * 0.5

    power = float(layer_cfg.get("shaping_power", 1.0))
    if power != 1.0:
        np.power(np.maximum(0.0, noise_normalized), power, out=noise_normalized)

    is_additive_only = bool(layer_cfg.get("additive_only", False))
    if not layer_cfg.get("is_base", False) and not layer_cfg.get("ridge", False) and not is_additive_only:
        noise_normalized = (noise_normalized * 2.0) - 1.0

    return noise_normalized


def scale_by_amplitude(noise: np.ndarray, layer_cfg: Dict) -> np.ndarray:
    """Шаг 3: Умножает нормализованный шум на его амплитуду в метрах."""
    amp = float(layer_cfg.get("amp_m", 0.0))
    return noise * amp


# --- Главная публичная функция-инструмент ---
def generate_noise_layer(
        seed: int, layer_cfg: Dict, coords_x: np.ndarray, coords_z: np.ndarray, cell_size: float
) -> np.ndarray:
    """
    Полный конвейер для создания одного слоя шума.
    Высокоуровневый "инструмент" для использования в terrain.py.
    """
    amp = float(layer_cfg.get("amp_m", 0.0))
    if amp <= 0:
        return np.zeros_like(coords_x)

    # Вызываем наши шаги-инструменты по очереди
    raw_noise = generate_base_noise(seed, layer_cfg, coords_x, coords_z, cell_size)
    shaped_noise = normalize_and_shape(raw_noise, layer_cfg)
    final_layer = scale_by_amplitude(shaped_noise, layer_cfg)

    return final_layer


def compute_amp_sum(preset) -> float:
    spectral = getattr(preset, "elevation", {}).get("spectral", {})
    total = float(spectral.get("continents", {}).get("amp_m", 0.0))
    for mask_cfg in spectral.get("masks", {}).values():
        for layer_cfg in mask_cfg.get("layers", {}).values():
            total += float(layer_cfg.get("amp_m", 0.0))
    return total