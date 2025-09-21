# Файл: game_engine_restructured/algorithms/terrain/nodes/effects.py
from __future__ import annotations

import math
from typing import Any, Dict
import numpy as np
from scipy.ndimage import gaussian_filter

from game_engine_restructured.numerics.fast_noise import fbm_grid_warped_bipolar


# Импортируем "математику" из numerics



# --- Нода "Умное террасирование" ---

def _calculate_curvature(height_grid: np.ndarray, cell_size: float) -> np.ndarray:
    """Вспомогательная функция: рассчитывает кривизну поверхности (Лапласиан)."""
    smoothed_h = gaussian_filter(height_grid, sigma=1.5, mode='reflect')
    gyy, gxx = np.gradient(np.gradient(smoothed_h, cell_size, axis=0), cell_size, axis=0), \
        np.gradient(np.gradient(smoothed_h, cell_size, axis=1), cell_size, axis=1)
    curvature = np.abs(gxx + gyy)
    return curvature


def apply_terracing(params: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Нода для применения эффекта "умных" террас, которые следуют за рельефом.
    """
    print("    [Effects] -> Применение 'умных' террас...")

    # --- ШАГ 1: Извлекаем данные из контекста и параметров ---
    height_grid = context["main_heightmap"]
    x_coords = context["x_coords"]
    z_coords = context["z_coords"]
    cell_size = context["cell_size"]
    seed = context["seed"]

    # Глобальная сила эффекта, если она задана
    # В оригинальной функции это была mask_strength, здесь мы упрощаем до общего множителя
    strength_multiplier = float(params.get("strength_multiplier", 1.0))

    step_h = float(params.get("step_height_m", 60.0))
    ledge_ratio = float(params.get("ledge_ratio", 0.7))
    strength_m = float(params.get("strength_m", 10.0))
    rnd: Dict[str, Any] = params.get("randomization", {})

    # --- ШАГ 2: Логика террасирования (взята 1-в-1 из terracing.py) ---
    phase = (height_grid / step_h) % 1.0

    gz, gx = np.gradient(height_grid, cell_size)
    warp_strength = float(rnd.get("warp_strength", 25.0))
    warped_x = x_coords + gx * warp_strength
    warped_z = z_coords + gz * warp_strength

    ledge_jitter = float(rnd.get("ledge_jitter", 0.0))
    ledge_scale = float(rnd.get("ledge_scale_tiles", 3000.0))
    if ledge_jitter != 0.0:
        n_ledge = fbm_grid_warped_bipolar(
            seed=seed + 23, coords_x=warped_x, coords_z=warped_z,
            freq0=1.0 / (ledge_scale * cell_size), octaves=2, ridge=True
        )
        ledge_local = np.clip(ledge_ratio * (1.0 + ledge_jitter * n_ledge), 0.5, 0.9)
    else:
        ledge_local = np.full_like(height_grid, np.clip(ledge_ratio, 0.05, 0.95))

    u = np.where(phase < ledge_local, phase / np.maximum(ledge_local, 1e-6),
                 (phase - ledge_local) / np.maximum(1.0 - ledge_local, 1e-6))
    bell = 1.0 - (2.0 * u - 1.0) ** 2
    sign = np.where(phase < ledge_local, 1.0, -0.75)
    deformation = sign * bell * strength_m

    curvature = _calculate_curvature(height_grid, cell_size)
    p95 = np.percentile(curvature, 95)
    curvature_norm = np.clip(curvature / (p95 + 1e-6), 0, 1)
    break_fade = max(1e-6, float(rnd.get("curvature_fade", 0.5)))
    break_mask = 1.0 - np.power(curvature_norm, break_fade)

    # --- ШАГ 3: Применяем результат ---
    final_deformation = deformation * break_mask * strength_multiplier

    context["main_heightmap"] = height_grid + final_deformation

    print("    [Effects] -> 'Умные' террасы успешно применены.")
    return context


def apply_selective_smoothing(params: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Нода, которая приглушает мелкие детали только на НЕ-склонах.
    """
    print("    [Effects] -> Применение выборочного сглаживания...")
    height_grid = context["main_heightmap"]
    cell_size = context["cell_size"]

    # --- Параметры из JSON ---
    angle_deg = float(params.get("angle_deg", 35.0))
    margin_cells = int(params.get("margin_cells", 3))
    detail_keep = float(params.get("detail_keep", 0.35))
    blur_iters = int(params.get("blur_iters", 1))

    # --- Логика функции (без изменений) ---
    H = height_grid
    gx = (np.roll(H, -1, axis=1) - np.roll(H, 1, axis=1)) / (2.0 * cell_size)
    gz = (np.roll(H, -1, axis=0) - np.roll(H, 1, axis=0)) / (2.0 * cell_size)
    tan_th = math.tan(math.radians(angle_deg))
    rock = (np.hypot(gx, gz) >= tan_th)

    m = rock.copy()
    for _ in range(max(0, margin_cells)):
        n = m | np.roll(m, 1, 0) | np.roll(m, -1, 0) | np.roll(m, 1, 1) | np.roll(m, -1, 1)
        m = n
    grass_w = (~m).astype(np.float32)

    A = H
    for _ in range(max(1, blur_iters)):
        c = (np.roll(A, (1, 1), (0, 1)) + np.roll(A, (1, -1), (0, 1)) + np.roll(A, (-1, 1), (0, 1)) + np.roll(A,
                                                                                                              (-1, -1),
                                                                                                              (0, 1)))
        e = (np.roll(A, (1, 0), (0, 1)) + np.roll(A, (-1, 0), (0, 1)) + np.roll(A, (0, 1), (0, 1)) + np.roll(A, (0, -1),
                                                                                                             (0, 1)))
        A = (4 * A + 2 * e + c) / 16.0
    H_base = A
    H_detail = H - H_base

    detail_scale = 1.0 - grass_w * (1.0 - float(detail_keep))

    context["main_heightmap"] = H_base + H_detail * detail_scale
    return context
# Сюда в будущем можно будет добавить и другие ноды-эффекты,
# например, selective_smooth_non_slopes из terrain_helpers.py