# Файл: game_engine_restructured/algorithms/terrain/nodes/noise.py (ВЕРСИЯ 2)
from __future__ import annotations
from typing import Any, Dict
import numpy as np

from game_engine_restructured.numerics.fast_noise import fbm_grid_warped_bipolar, fbm_amplitude


def _generate_noise_field(params: Dict[str, Any], context: Dict[str, Any]) -> np.ndarray:
    """
    УНИВЕРСАЛЬНЫЙ ИНСТРУМЕНТ: Генерирует массив шума по параметрам, но не применяет его.
    """
    # --- Шаги 1-4: Генерация и формирование шума (без изменений) ---
    x_coords = context["x_coords"]
    z_coords = context["z_coords"]
    cell_size = context["cell_size"]
    layer_seed = context["seed"] + params.get("seed_offset", 0)

    is_additive = bool(params.get("additive_only", True))
    warp_cfg = params.get("warp", {})
    gain = float(params.get("gain", 0.5))
    octaves = int(params.get("octaves", 4))

    noise_params = {
        "seed": layer_seed, "coords_x": x_coords, "coords_z": z_coords,
        "freq0": 1.0 / (params.get("scale_tiles", 1000.0) * cell_size + 1e-6),
        "octaves": octaves, "ridge": bool(params.get("ridge", False)), "gain": gain,
        "lacunarity": float(params.get("lacunarity", 2.0)), "warp_seed": layer_seed + 54321,
        "warp_amp": float(warp_cfg.get("amp", 0.0)),
        "warp_freq": 1.0 / (warp_cfg.get("scale_tiles", 1000.0) * cell_size + 1e-6),
        "warp_octaves": int(warp_cfg.get("octaves", 2))
    }

    raw_unnormalized_noise = fbm_grid_warped_bipolar(**noise_params)
    max_amp = fbm_amplitude(gain, octaves)
    normalized_noise = raw_unnormalized_noise / max_amp if max_amp > 1e-6 else raw_unnormalized_noise

    noise_for_shaping = (normalized_noise + 1.0) * 0.5 if is_additive else np.abs(normalized_noise)
    shaping_power = float(params.get("shaping_power", 1.0))
    shaped_noise = np.power(noise_for_shaping, shaping_power) if shaping_power != 1.0 else noise_for_shaping
    final_normalized_noise = shaped_noise if is_additive else np.sign(normalized_noise) * shaped_noise

    amp_m = float(params.get("amp_m", 0.0))
    return final_normalized_noise * amp_m


def generate_layer(params: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """
    НОДА типа "noise": Генерирует слой FBM-шума и применяет его к основной карте высот.
    """
    # --- ШАГ 1: Генерируем шум с помощью нашего нового инструмента ---
    final_noise = _generate_noise_field(params, context)

    # --- ШАГ 2: Применяем результат к основной карте высот ---
    blend_mode = params.get("blend_mode", "add")
    if blend_mode == "replace":
        context["main_heightmap"] = final_noise
    else:
        context["main_heightmap"] += final_noise

    # --- ШАГ 3: Возвращаем обновленный контекст ---
    return context