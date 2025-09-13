# ==============================================================================
# Файл: game_engine_restructured/algorithms/terrain/terrain.py
# Назначение: Генерация геометрии ландшафта (карты высот).
# ВЕРСЯ 4.0: С правильным порядком операций для предсказуемого результата.
# ==============================================================================
from __future__ import annotations
from typing import Any
import numpy as np
from scipy.ndimage import gaussian_filter

from ...core.noise.fast_noise import fbm_grid, fbm_amplitude


# ==============================================================================
# --- Вспомогательные утилиты ---
# ==============================================================================

def _apply_shaping_curve(grid: np.ndarray, power: float) -> None:
    """Применяет степенную кривую для увеличения контраста."""
    if power != 1.0:
        np.power(grid, power, out=grid)


def _quantize_heights(grid: np.ndarray, step: float) -> None:
    """Квантует высоты (создает "террасы")."""
    if step > 0:
        np.round(grid / step, out=grid)
        grid *= step


def _print_range(tag: str, arr: np.ndarray) -> None:
    """Выводит в консоль минимальное и максимальное значение массива."""
    mn, mx = float(np.min(arr)), float(np.max(arr))
    print(f"[CHECK] {tag}: min={mn:.2f} max={mx:.2f} rng={mx - mn:.2f}")


# ==============================================================================
# --- Основная функция генерации рельефа ---
# ==============================================================================

def generate_elevation_region(
        seed: int, scx: int, scz: int,
        region_size_chunks: int, chunk_size: int,
        preset: Any, scratch_buffers: dict
) -> np.ndarray:
    # --- ШАГ 0: Чтение настроек ---
    cfg = getattr(preset, "elevation", {})
    spectral_cfg = cfg.get("spectral", {}) or {}
    ext_size = (region_size_chunks + 2) * chunk_size
    cell_size = float(getattr(preset, "cell_size", 1.0))

    base_wx = (scx * region_size_chunks - 1) * chunk_size
    base_wz = (scz * region_size_chunks - 1) * chunk_size

    height_grid = np.zeros((ext_size, ext_size), dtype=np.float32)

    # --- ШАГ 1: Генерируем и формируем БАЗОВЫЙ МАКРОРЕЛЬЕФ (континенты) ---
    continents_cfg = spectral_cfg.get("continents", {})
    amp_cont = float(continents_cfg.get("amp_m", 0.0))
    if amp_cont > 0:
        # Генерируем шум для континентов
        noise = fbm_grid(
            seed=seed, x0_px=base_wx, z0_px=base_wz, size=ext_size, mpp=cell_size,
            freq0=1.0 / (float(continents_cfg.get("scale_tiles", 1000)) * cell_size),
            octaves=int(continents_cfg.get("octaves", 3)),
            ridge=bool(continents_cfg.get("ridge", False)),
            rot_deg=float(continents_cfg.get("rotation_deg", 0.0))
        )
        # Нормализуем его по фактическому диапазону в [0, 1]
        min_val, max_val = np.min(noise), np.max(noise)
        if (max_val - min_val) > 1e-6:
            noise = (noise - min_val) / (max_val - min_val)

        # Применяем контраст
        _apply_shaping_curve(noise, float(cfg.get("shaping_power", 1.0)))

        # Добавляем в итоговую карту высот с нужной амплитудой
        height_grid += noise * amp_cont

    # --- ШАГ 2: Добавляем СРЕДНИЕ и МЕЛКИЕ детали ПОВЕРХ базового рельефа ---
    for i, layer_name in enumerate(["hills", "detail"]):
        layer_cfg = spectral_cfg.get(layer_name, {})
        amp = float(layer_cfg.get("amp_m", 0.0))
        if amp <= 0: continue

        octaves = int(layer_cfg.get("octaves", 4))
        noise = fbm_grid(
            seed=seed + i + 1, x0_px=base_wx, z0_px=base_wz, size=ext_size, mpp=cell_size,
            freq0=1.0 / (float(layer_cfg.get("scale_tiles", 200)) * cell_size),
            octaves=octaves,
            ridge=bool(layer_cfg.get("ridge", False)),
            rot_deg=float(layer_cfg.get("rotation_deg", 0.0))
        )
        # Нормализуем шум в диапазон [-1, 1], чтобы он добавлял детали и вверх, и вниз
        norm_factor = fbm_amplitude(0.5, octaves)
        if norm_factor > 1e-6:
            noise /= norm_factor

        height_grid += noise * amp

    # --- ШАГ 3: Финальная постобработка ---
    max_h_config = float(cfg.get("max_height_m", 150.0))
    base_height_config = float(cfg.get("base_height_m", 0.0))
    smoothing_passes = int(cfg.get("smoothing_passes", 0))

    # Применяем сглаживание к итоговой карте
    if smoothing_passes > 0:
        sigma = 0.6 * smoothing_passes
        # Используем безопасный буфер для сглаживания
        gaussian_filter(height_grid, sigma=sigma, output=scratch_buffers['b'], mode='reflect')
        height_grid = np.copy(scratch_buffers['b'])

    # Применяем базовую высоту и обрезаем по максимуму
    height_grid += base_height_config
    np.clip(height_grid, 0, max_h_config, out=height_grid)

    _print_range("height_final", height_grid)

    return height_grid.copy()