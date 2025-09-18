# Файл: game_engine_restructured/algorithms/terrain/terrain_helpers.py
from __future__ import annotations

import math
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
    octaves = int(layer_cfg.get("octaves", 4))
    norm_factor = max(fbm_amplitude(0.5, octaves), 1e-6)
    noise_normalized = noise / norm_factor

    is_base  = bool(layer_cfg.get("is_base", False))
    is_ridge = bool(layer_cfg.get("ridge", False))
    is_add   = bool(layer_cfg.get("additive_only", False))
    power    = float(layer_cfg.get("shaping_power", 1.0))

    # База → [0,1]
    if is_base and not is_ridge:
        noise_normalized = (noise_normalized + 1.0) * 0.5

    if is_ridge or is_add:
        # ВЕТКА «только добавлять»: диапазон [0,1]
        np.maximum(0.0, noise_normalized, out=noise_normalized)
        if power != 1.0:
            np.power(noise_normalized, power, out=noise_normalized)

        # МЯГКИЙ ПОЛ: поднимем минимум до positive_floor (если задан)
        floor = float(layer_cfg.get("positive_floor", 0.0))
        if floor > 0.0:
            # маппинг [0..1] → [floor..1]
            noise_normalized = floor + (1.0 - floor) * noise_normalized

    else:
        # ВЕТКА двуполярная: [-1,1]
        if power != 1.0:
            np.power(np.maximum(0.0, noise_normalized), power, out=noise_normalized)
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


def _get(obj, key, default):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)

def compute_amp_sum(preset) -> float:
    elev = _get(preset, "elevation", {}) or {}
    spectral = elev.get("spectral", {}) if isinstance(elev, dict) else _get(elev, "spectral", {})
    total = float((spectral.get("continents", {}) if isinstance(spectral, dict) else _get(spectral, "continents", {})).get("amp_m", 0.0))
    masks = spectral.get("masks", {}) if isinstance(spectral, dict) else _get(spectral, "masks", {})
    for mask_cfg in (masks or {}).values():
        layers = mask_cfg.get("layers", {}) if isinstance(mask_cfg, dict) else _get(mask_cfg, "layers", {})
        for layer_cfg in (layers or {}).values():
            total += float(layer_cfg.get("amp_m", 0.0))
    return total


def selective_smooth_non_slopes(
    height: np.ndarray,
    *,
    cell_size: float,
    angle_deg: float = 35.0,   # что считаем «скалой»
    margin_cells: int = 3,     # отступ от скал (расширяем «запрет»)
    detail_keep: float = 0.35, # сколько мелкой ряби оставить на траве
    blur_iters: int = 1,       # сколько раз применить 3x3 фильтр
    region_weight: np.ndarray | None = None,  # [0..1], где применять (мультипликативно)
) -> np.ndarray:
    """Приглушает мелкие детали только на НЕ-склонах, опционально внутри заданного региона."""
    H = height

    # 1) Маска крутых склонов по углу (в метрах)
    gx = (np.roll(H, -1, axis=1) - np.roll(H, 1, axis=1)) / (2.0 * cell_size)
    gz = (np.roll(H, -1, axis=0) - np.roll(H, 1, axis=0)) / (2.0 * cell_size)
    tan_th = math.tan(math.radians(angle_deg))
    rock = (np.hypot(gx, gz) >= tan_th)

    # 2) Дилатация скал (расширяем «запретную» область)
    m = rock.copy()
    for _ in range(max(0, margin_cells)):
        n = m | np.roll(m,1,0) | np.roll(m,-1,0) | np.roll(m,1,1) | np.roll(m,-1,1) \
              | np.roll(np.roll(m,1,0),1,1) | np.roll(np.roll(m,1,0),-1,1) \
              | np.roll(np.roll(m,-1,0),1,1) | np.roll(np.roll(m,-1,0),-1,1)
        m = n
    grass_w = (~m).astype(np.float32)  # 1 — где можно сглаживать, 0 — где нельзя

    if region_weight is not None:
        # сузить действие в пределах региона (например, только «горы»)
        grass_w *= region_weight.astype(np.float32)

    # 3) База/деталь через лёгкое сглаживание 3×3 (аппрокс. гаусс)
    A = H
    for _ in range(max(1, blur_iters)):
        c = (np.roll(A,(1,1),(0,1)) + np.roll(A,(1,-1),(0,1))
           +  np.roll(A,(-1,1),(0,1)) + np.roll(A,(-1,-1),(0,1)))
        e = (np.roll(A,(1,0),(0,1)) + np.roll(A,(-1,0),(0,1))
           +  np.roll(A,(0,1),(0,1)) + np.roll(A,(0,-1),(0,1)))
        A = (4*A + 2*e + c) / 16.0
    H_base = A
    H_detail = H - H_base

    # 4) На траве оставляем detail_keep, на скалах — 100%
    detail_scale = 1.0 - grass_w * (1.0 - float(detail_keep))
    return H_base + H_detail * detail_scale