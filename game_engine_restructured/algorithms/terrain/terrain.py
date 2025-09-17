# ==============================================================================
# Файл: game_engine_restructured/algorithms/terrain/terrain.py
# Назначение: Генерация геометрии ландшафта (карты высот).
# ВЕРСИЯ 23.0 (Стабильная): Возвращена поддержка shaping_power.
#              Код стабилизирован для работы с трехслойной системой.
# ==============================================================================

from __future__ import annotations

import math
from typing import Any, Dict

import numpy as np
from numba import njit

from .slope import compute_slope_mask, _apply_slope_limiter
from ...core.noise.fast_noise import fbm_amplitude, fbm_grid_warped


@njit(cache=True, fastmath=True, parallel=True)
def _create_mask(base_noise: np.ndarray, threshold: float, invert: bool, fade_range: float) -> np.ndarray:
    """
    Создает маску [0,1] из базового шума по заданным правилам порога, инверсии и плавного перехода.
    """
    h, w = base_noise.shape
    output = np.empty_like(base_noise)

    # Определяем границы плавного перехода (fade)
    fade_half = max(0.0, fade_range / 2.0)
    t0 = threshold - fade_half
    t1 = threshold + fade_half

    for i in prange(h):
        for j in range(w):
            val = base_noise[i, j]

            # Рассчитываем положение точки внутри зоны перехода [0, 1]
            t = (val - t0) / (t1 - t0) if (t1 - t0) > 1e-6 else 0.0

            # Ограничиваем t в диапазоне [0, 1]
            t = max(0.0, min(1.0, t))

            # Применяем формулу Smoothstep для S-образного плавного перехода
            smooth_val = t * t * (3.0 - 2.0 * t)

            if invert:
                output[i, j] = 1.0 - smooth_val
            else:
                output[i, j] = smooth_val

    return output

def _print_range(tag: str, arr: np.ndarray) -> None:
    mn, mx = float(np.min(arr)), float(np.max(arr))
    print(f"[DIAGNOSTIC] {tag}: min={mn:.3f} max={mx:.3f} range={mx - mn:.3f}")


def _generate_layer(
        seed: int, layer_cfg: Dict, base_coords_x: np.ndarray, base_coords_z: np.ndarray,
        cell_size: float
) -> np.ndarray:
    amp = float(layer_cfg.get("amp_m", 0.0))
    if amp <= 0:
        return np.zeros_like(base_coords_x)

    octaves = int(layer_cfg.get("octaves", 4))
    is_ridge = bool(layer_cfg.get("ridge", False))
    scale = float(layer_cfg.get("scale_tiles", 1000)) * cell_size
    freq = 1.0 / scale if scale > 0 else 0.0

    # --- НОВЫЙ БЛОК: Собираем параметры варпинга в словарь ---
    warp_params = {}
    warp_cfg = layer_cfg.get("warp")
    if warp_cfg:
        warp_scale = float(warp_cfg.get("scale_tiles", 1000)) * cell_size

        warp_params = {
            "warp_seed": seed + 7,
            "warp_amp": float(warp_cfg.get("amp", 0.0)),
            "warp_octaves": int(warp_cfg.get("octaves", 2)),
            "warp_freq": 1.0 / warp_scale if warp_scale > 0 else 0.0
        }

    # --- ИЗМЕНЕННЫЙ ВЫЗОВ: передаем параметры через распаковку словаря ---
    # Оператор ** развернет наш словарь в именованные аргументы,
    # которые ожидает функция.
    noise = fbm_grid_warped(
        seed=seed,
        coords_x=base_coords_x,
        coords_z=base_coords_z,
        freq0=freq,
        octaves=octaves,
        ridge=is_ridge,
        **warp_params  # Если warp_params пустой, сюда ничего не добавится
    )

    norm_factor = max(fbm_amplitude(0.5, octaves), 1e-6)
    noise_normalized = noise / norm_factor

    # Базовый слой (is_base) всегда должен быть в диапазоне [0, 1] перед умножением на амплитуду
    if layer_cfg.get("is_base", False):
        if not is_ridge:
            noise_normalized = (noise_normalized + 1.0) * 0.5

    # --- ВОТ ОН: ПРИМЕНЕНИЕ SHAPING_POWER ---
    power = float(layer_cfg.get("shaping_power", 1.0))
    if power != 1.0:
        # Убеждаемся, что работаем с положительными значениями для возведения в степень
        np.power(np.maximum(0.0, noise_normalized), power, out=noise_normalized)

    # Для слоев, которые не являются базовыми, возвращаем диапазон [-amp, amp]
    # --- ВОТ ОН, НАШ ПРЕДОХРАНИТЕЛЬ ---
    is_additive_only = bool(layer_cfg.get("additive_only", False))

    # Для слоев, которые не являются базовыми, не ridge И НЕ являются чисто аддитивными
    if not layer_cfg.get("is_base", False) and not is_ridge and not is_additive_only:
        # Возвращаем диапазон [-amp, amp] ("плюс-минус")
        noise_normalized = (noise_normalized * 2.0) - 1.0

    return noise_normalized * amp


def generate_elevation_region(
        seed: int, scx: int, scz: int, region_size_chunks: int, chunk_size: int, preset: Any, scratch_buffers: dict,
) -> np.ndarray:
    cfg = getattr(preset, "elevation", {})
    spectral_cfg = cfg.get("spectral", {}) or {}
    ext_size = (region_size_chunks + 2) * chunk_size
    cell_size = float(getattr(preset, "cell_size", 1.0))
    base_wx = (scx * region_size_chunks - 1) * chunk_size
    base_wz = (scz * region_size_chunks - 1) * chunk_size
    z_coords_base, x_coords_base = np.mgrid[0:ext_size, 0:ext_size]
    x_coords_base = (x_coords_base.astype(np.float32) + base_wx) * cell_size
    z_coords_base = (z_coords_base.astype(np.float32) + base_wz) * cell_size

    # --- ЭТАП 1: Генерируем каждый слой в отдельный массив ---
    continents_layer = np.zeros_like(x_coords_base)
    if "continents" in spectral_cfg:
        continents_layer = _generate_layer(seed, spectral_cfg["continents"], x_coords_base,
                                           z_coords_base, cell_size)

    features_layer = np.zeros_like(x_coords_base)
    if "large_features" in spectral_cfg:
        features_layer = _generate_layer(seed + 1, spectral_cfg["large_features"], x_coords_base, z_coords_base,
                                         cell_size)

    detail_layer = np.zeros_like(x_coords_base)
    if "detail" in spectral_cfg:
        detail_layer = _generate_layer(seed + 2, spectral_cfg["detail"], x_coords_base, z_coords_base,
                                       cell_size)

    # --- ЭТАП 2: Выбираем метод смешивания слоев ---
    use_advanced_modulation = bool(spectral_cfg.get("use_advanced_modulation", False))

    if use_advanced_modulation:
        # Новый, продвинутый метод
        height_grid = _apply_advanced_modulation(
            continents_layer, features_layer, detail_layer, preset
        )
    else:
        # Старый метод простого сложения
        print("[DIAGNOSTIC] Using SIMPLE ADDITIVE pipeline.")
        height_grid = continents_layer + features_layer + detail_layer

    # --- ЭТАП 3: Финальные шаги ---
    height_grid += float(cfg.get("base_height_m", 0.0))
    np.clip(height_grid, 0.0, float(cfg.get("max_height_m", 150.0)), out=height_grid)

    # --- ЭТАП 4: ОГРАНИЧЕНИЕ МАКСИМАЛЬНОГО УКЛОНА ---
    # Добавляем этот блок
    if spectral_cfg.get("use_slope_limiter", False):
        max_angle_deg = float(spectral_cfg.get("slope_limiter_angle_deg", 75.0))
        iterations = int(spectral_cfg.get("slope_limiter_iterations", 4))
        max_slope_tangent = math.tan(math.radians(max_angle_deg))

        # Вызываем функцию из slope.py (предполагая, что она импортирована)
        _apply_slope_limiter(height_grid, max_slope_tangent, cell_size, iterations)
        print(f"[DIAGNOSTIC] Slope limiter applied with max angle {max_angle_deg} deg.")

    _print_range("height_final", height_grid)
    return height_grid.copy()


def _apply_advanced_modulation(
        continents: np.ndarray, features: np.ndarray, detail: np.ndarray, preset: Any
) -> np.ndarray:
    """
    Применяет двухуровневую генерацию для Гор и Равнин.
    """
    print("[DIAGNOSTIC] Using 2-pipeline generation (Mountains/Plains).")

    spectral_cfg = getattr(preset, "elevation", {}).get("spectral", {})
    masks_cfg = spectral_cfg.get("masks", {})
    continents_cfg = spectral_cfg.get("continents", {})

    # --- ЭТАП 1: Нормализация и создание масок ---
    continents_amp = float(continents_cfg.get("amp_m", 1.0))
    continents_norm = continents / max(continents_amp, 1e-6)

    # Создаем маски, читая конфиг из JSON
    mountain_mask_cfg = masks_cfg.get("mountains", {})
    plains_mask_cfg = masks_cfg.get("plains", {})

    mountain_mask = _create_mask(
        continents_norm,
        float(mountain_mask_cfg.get("threshold", 0.5)),
        bool(mountain_mask_cfg.get("invert", False)),
        float(mountain_mask_cfg.get("fade_range", 0.0))
    )
    plains_mask = _create_mask(
        continents_norm,
        float(plains_mask_cfg.get("threshold", 0.5)),
        bool(plains_mask_cfg.get("invert", True)),
        float(plains_mask_cfg.get("fade_range", 0.0))
    )

    # --- ЭТАП 2: Два независимых конвейера ---
    # !!ВАЖНО!!: Сейчас оба конвейера используют одни и те же слои `features` и `detail`.
    # В будущем вы сможете создать отдельные слои, например, `plains_features`, `mountain_detail` и т.д.

    # Горный конвейер (пока используем существующие слои)
    mountain_contribution = (features + detail) * mountain_mask

    # Равнинный конвейер (пока что он пустой, т.к. нет отдельных слоев для равнин)
    # plains_hills = _generate_layer(...)
    # plains_contribution = plains_hills * plains_mask
    plains_contribution = np.zeros_like(continents)

    # --- ЭТАП 3: Финальное сложение ---
    final_grid = continents + mountain_contribution + plains_contribution

    return final_grid