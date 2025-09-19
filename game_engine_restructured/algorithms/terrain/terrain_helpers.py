# Файл: game_engine_restructured/algorithms/terrain/terrain_helpers.py
from __future__ import annotations

import math
from typing import Any, Dict
import numpy as np

# Импортируем "математику" из numerics и core
from ...numerics.fast_noise import fbm_grid_warped, fbm_amplitude, fbm_grid_warped_bipolar


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

    # --- НАЧАЛО ИСПРАВЛЕНИЯ ---

    # 1. Вызываем сырой, ненормализованный шум, как и раньше
    raw_noise = fbm_grid_warped(
        seed=seed, coords_x=coords_x, coords_z=coords_z, freq0=freq,
        octaves=octaves, ridge=is_ridge, **warp_params
    )

    # 2. Теперь нормализуем его
    # Так как эта функция не читает 'gain' из конфига, мы используем
    # значение по умолчанию (0.5), которое используется внутри fbm_grid_warped.
    gain = 0.5
    max_amp = fbm_amplitude(gain, octaves)

    if max_amp > 1e-6:
        normalized_noise = raw_noise / max_amp
    else:
        normalized_noise = raw_noise

    return normalized_noise


def normalize_and_shape(noise: np.ndarray, layer_cfg: Dict) -> np.ndarray:
    octaves = int(layer_cfg.get("octaves", 4))
    noise_normalized = noise.astype(np.float32, copy=False)

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
        layer_seed: int,
        layer_cfg: Dict[str, Any],
        x_coords: np.ndarray,
        z_coords: np.ndarray,
        cell_size: float
) -> np.ndarray:
    # --- ШАГ 1: Собираем ВСЕ параметры для шума в один словарь ---
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

    # --- ШАГ 2: Вызываем "сырой", ненормализованный шум ---
    # Мы всегда используем bipolar, т.к. даже аддитивному шуму нужна нормализация из [-1, 1]
    raw_unnormalized_noise = fbm_grid_warped_bipolar(**noise_params)

    # --- ШАГ 3: Нормализуем его до честного диапазона [-1, 1] ---
    max_amp = fbm_amplitude(gain, octaves)
    if max_amp > 1e-6:
        normalized_noise = raw_unnormalized_noise / max_amp
    else:
        normalized_noise = raw_unnormalized_noise

    # --- ШАГ 4: Обрабатываем additive_only и shaping_power ---
    if is_additive:
        noise_for_shaping = (normalized_noise + 1.0) * 0.5  # -> [0, 1]
    else:
        noise_for_shaping = np.abs(normalized_noise)  # -> [0, 1]

    shaping_power = float(layer_cfg.get("shaping_power", 1.0))
    if shaping_power != 1.0:
        shaped_noise = np.power(noise_for_shaping, shaping_power)
    else:
        shaped_noise = noise_for_shaping

    if not is_additive:
        final_normalized_noise = np.sign(normalized_noise) * shaped_noise
    else:
        final_normalized_noise = shaped_noise

    # --- ШАГ 5: Масштабируем до амплитуды ---
    amp_m = float(layer_cfg.get("amp_m", 0.0))
    final_noise = final_normalized_noise * amp_m

    return final_noise


def _get(obj, key, default):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)

def compute_amp_sum(preset) -> float:
    """
    "Умный" расчет H_NORM. Суммирует только те амплитуды, которые могут
    сложиться в самой высокой точке мира. Игнорирует маски с "invert": true.
    """
    elev = _get(preset, "elevation", {}) or {}
    spectral = elev.get("spectral", {}) if isinstance(elev, dict) else _get(elev, "spectral", {})

    # 1. Начинаем с базовой высоты континента
    total = float((spectral.get("continents", {}) if isinstance(spectral, dict) else _get(spectral, "continents", {})).get("amp_m", 0.0))

    # 2. Перебираем все маски
    masks = spectral.get("masks", {}) if isinstance(spectral, dict) else _get(spectral, "masks", {})
    for mask_name, mask_cfg in (masks or {}).items():
        # 3. КЛЮЧЕВАЯ ПРОВЕРКА: Если маска инвертирована ("invert": true),
        #    она активна в низинах и не может влиять на максимальную высоту. Пропускаем ее.
        if mask_cfg.get("invert", False):
            print(f"[H_NORM] -> Пропускаем маску '{mask_name}', так как она инвертирована.")
            continue

        # 4. Если маска не инвертирована, значит она активна на вершинах.
        #    Суммируем амплитуды всех ее слоев.
        print(f"[H_NORM] -> Учитываем маску '{mask_name}' для расчета максимальной высоты.")
        layers = mask_cfg.get("layers", {}) if isinstance(mask_cfg, dict) else _get(mask_cfg, "layers", {})
        for layer_cfg in (layers or {}).values():
            total += float(layer_cfg.get("amp_m", 0.0))

    # 5. Добавляем базовую высоту, если она есть
    total += float(elev.get("base_height_m", 0.0))

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


def _morph_wave_ridge(n, k, sharpness_enhance=0.0):
    """
    Морф одной октавы n∈[-1,1] между billow/base/ridge по карте k∈[-1,1].
    k>0 → ridge, k<0 → billow, k≈0 → base. sharpness_enhance ≥ 0 усиливает «остроту».
    """
    import numpy as np

    n = np.clip(n, -1.0, 1.0).astype(np.float32)
    k = np.clip(k, -1.0, 1.0).astype(np.float32)

    t_r = np.maximum(0.0, k)       # доля ridge
    t_b = np.maximum(0.0, -k)      # доля billow
    b = 2.0 * np.abs(n) - 1.0      # billow ∈ [-1,1]
    r = 1.0 - 2.0 * np.abs(n)      # ridge  ∈ [-1,1]

    out = n * (1.0 - t_r - t_b) + r * t_r + b * t_b
    if sharpness_enhance > 0.0:
        s = 1.0 + float(sharpness_enhance)
        out = np.sign(out) * (np.abs(out) ** s)

    return np.clip(out, -1.0, 1.0).astype(np.float32)