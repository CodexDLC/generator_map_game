# ==============================================================================
# Файл: game_engine_restructured/algorithms/terrain/terrain.py
# Назначение: Генерация исключительно геометрии ландшафта (карты высот).
# ВЕРСИЯ С NUMBA-УСКОРЕНИЕМ
# ==============================================================================
from __future__ import annotations
from typing import Any
import numpy as np
from opensimplex import OpenSimplex  # Оставляем для совместимости, если понадобится
from ...core.noise.fast_noise import fbm_grid, fbm_amplitude




# --- КОНЕЦ ИЗМЕНЕНИЙ 1 ---

# --- Утилиты (остаются без изменений) ---
def _apply_shaping_curve(grid: np.ndarray, power: float) -> None:
    if power == 1.0: return
    np.power(grid, power, out=grid)


def _smooth_grid(grid: np.ndarray, passes: int, scratch_buffer: np.ndarray) -> np.ndarray:
    if passes <= 0: return grid
    from scipy.ndimage import gaussian_filter
    sigma = 0.6 * passes
    gaussian_filter(grid, sigma=sigma, output=scratch_buffer, mode='reflect')
    return scratch_buffer


def _quantize_heights(grid: np.ndarray, step: float) -> None:
    if step <= 0: return
    np.round(grid / step, out=grid)
    grid *= step


def _print_range(tag: str, arr: np.ndarray) -> None:
    mn, mx = float(np.min(arr)), float(np.max(arr))
    print(f"[CHECK] {tag}: min={mn:.4f} max={mx:.4f} rng={mx - mn:.6f}")


# ==============================================================================
# --- БЛОК 2: Основная функция генерации рельефа (ОБНОВЛЕННАЯ) ---
# ==============================================================================
def generate_elevation_region(
        seed: int, scx: int, scz: int,
        region_size_chunks: int, chunk_size: int,
        preset: Any, scratch_buffers: dict
) -> np.ndarray:
    # --- Шаг 1: Чтение настроек (без изменений) ---
    cfg = getattr(preset, "elevation", {})
    spectral_cfg = cfg.get("spectral", {}) or {}
    warp_cfg = cfg.get("warp", {}) or {}

    ext_size = (region_size_chunks + 2) * chunk_size
    height_grid = scratch_buffers['a']
    height_grid.fill(0.0)

    # --- Шаг 2: Подготовка (без изменений) ---
    # Оставляем OpenSimplex только для warp, так как он там используется
    warp_x_gen = OpenSimplex(seed ^ 0xCAFEF00D)
    warp_z_gen = OpenSimplex(seed ^ 0xDEADBEEF)

    base_wx = (scx * region_size_chunks - 1) * chunk_size
    base_wz = (scz * region_size_chunks - 1) * chunk_size

    # --- НАЧАЛО ИЗМЕНЕНИЙ 2: Оптимизация WARP ---
    # Мы все еще используем циклы для warp, но это можно будет оптимизировать в будущем.
    # Главное ускорение будет в генерации самих шумов.
    warp_scale = float(warp_cfg.get("scale_tiles", 1.0))
    warp_strength = float(warp_cfg.get("strength_m", 0.0))
    if warp_scale > 0.0 and warp_strength > 0.0:
        print("  -> Calculating warp fields (can be slow)...")
        warp_freq = 1.0 / warp_scale

        # Создаем сетку оригинальных координат один раз
        wx_1d_orig = base_wx + np.arange(ext_size, dtype=np.float32)
        wz_1d_orig = base_wz + np.arange(ext_size, dtype=np.float32)
        wx_grid_orig, wz_grid_orig = np.meshgrid(wx_1d_orig, wz_1d_orig, indexing="xy")

        warp_field_x = scratch_buffers['b']
        warp_field_z = np.empty_like(warp_field_x)

        for z in range(ext_size):
            for x in range(ext_size):
                orig_x, orig_z = wx_grid_orig[z, x], wz_grid_orig[z, x]
                warp_field_x[z, x] = warp_x_gen.noise2(orig_x * warp_freq, orig_z * warp_freq)
                warp_field_z[z, x] = warp_z_gen.noise2(orig_x * warp_freq, orig_z * warp_freq)

        wx_grid = wx_grid_orig + warp_field_x * warp_strength
        wz_grid = wz_grid_orig + warp_field_z * warp_strength
    else:
        # Если warp отключен, создаем сетку один раз
        wx_1d = base_wx + np.arange(ext_size, dtype=np.float32)
        wz_1d = base_wz + np.arange(ext_size, dtype=np.float32)
        wx_grid, wz_grid = np.meshgrid(wx_1d, wz_1d, indexing="xy")
    # --- КОНЕЦ ИЗМЕНЕНИЙ 2 ---

    # --- Шаг 4: Смешивание слоев шума (ЗАМЕНЯЕМ НА NUMBA) ---
    print("  -> Generating spectral layers (Numba-accelerated)...")
    ordered_layers = [spectral_cfg[k] for k in ("continents", "hills", "detail") if k in spectral_cfg]
    total_amp = sum(float(l.get("amp_m", 0.0)) for l in ordered_layers) or 1.0

    cell_size = float(getattr(preset, "cell_size", 1.0))

    for i, layer_cfg in enumerate(ordered_layers):
        amp = float(layer_cfg.get("amp_m", 0.0))
        if amp <= 0.0: continue

        scale_tiles = float(layer_cfg.get("scale_tiles", 1.0))
        freq = 1.0 / (scale_tiles * cell_size)  # Частота в мировых координатах (метрах)
        octaves = int(layer_cfg.get("octaves", 1))

        # --- ГЛАВНОЕ УСКОРЕНИЕ ---
        # Вызываем быструю Numba-функцию, которая вернет целый массив шума
        noise_layer = fbm_grid(
            seed=seed + i,  # Уникальный сид для каждого слоя
            x0_px=base_wx,
            z0_px=base_wz,
            size=ext_size,
            mpp=cell_size,
            freq0=freq,
            octaves=octaves,
            lacunarity=2.0,
            gain=0.5,
            rot_deg=0.0  # ridge пока не поддерживается в Numba-версии, но это можно добавить
        )

        # Нормализуем и добавляем к общей карте высот
        norm_factor = fbm_amplitude(0.5, octaves)
        height_grid += (noise_layer / norm_factor) * amp

    # --- Шаг 5: Постобработка и масштабирование в метры ---
    # Этот блок приводит "сырой" шум к финальным высотам в метрах.
    max_h = float(cfg.get("max_height_m", 150.0))
    base_height = float(cfg.get("base_height_m", 0.0))

    # --- НАЧАЛО ИЗМЕНЕНИЙ ---

    # 5.1. Нормализуем диапазон [-total_amp, +total_amp] в [0, 1]
    # Для этого сначала сдвигаем его в [0, 2*total_amp], а затем делим.
    if total_amp > 0:
        height_grid = (height_grid + total_amp) / (2 * total_amp)

    # 5.2. Теперь безопасно применяем контраст к диапазону [0, 1]
    _apply_shaping_curve(height_grid, float(cfg.get("shaping_power", 1.0)))

    # 5.3. Растягиваем диапазон [0, 1] до реальной высоты в метрах [0, max_h]
    height_grid *= max_h

    # 5.4. Применяем глобальный сдвиг высоты в метрах
    if base_height != 0.0:
        height_grid += base_height

    # 5.5. Сглаживание и квантование (применяются к финальным высотам)
    smoothed = _smooth_grid(height_grid, int(cfg.get("smoothing_passes", 0)), scratch_buffers['b'])
    _quantize_heights(smoothed, float(cfg.get("quantization_step_m", 0.0)))

    # 5.6. Финальная "обрезка" высот, чтобы они не выходили за максимум
    _print_range("height_before_clip", smoothed)
    np.clip(smoothed, 0, max_h, out=smoothed)

    # --- КОНЕЦ ИЗМЕНЕНИЙ ---

    # --- Шаг 6: Возвращаем результат ---
    return smoothed.copy()