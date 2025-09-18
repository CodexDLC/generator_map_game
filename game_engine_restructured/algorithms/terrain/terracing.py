import numpy as np
from numba import njit, prange

from game_engine_restructured.algorithms.terrain.terrain_helpers import generate_noise_layer


@njit(cache=True, fastmath=True, parallel=True)
def _calculate_terrace_deformation(
        height_grid: np.ndarray,
        terrace_height: float,
        ledge_width_ratio: float,
        strength_m: float
) -> np.ndarray:
    """
    Рассчитывает "идеальную" деформацию для создания непрерывных террас.
    """
    deformation_grid = np.zeros_like(height_grid)
    ledge_point = terrace_height * ledge_width_ratio

    for z in prange(height_grid.shape[0]):
        for x in range(height_grid.shape[1]):
            h = height_grid[z, x]
            step_pos = h % terrace_height

            if step_pos < ledge_point:
                t = step_pos / ledge_point
                deformation = t * strength_m
            else:
                t = (step_pos - ledge_point) / (terrace_height - ledge_point)
                deformation = (1.0 - t) * strength_m - strength_m

            deformation_grid[z, x] = deformation

    return deformation_grid


def apply_terracing_effect(
        height_grid: np.ndarray,
        mountain_mask: np.ndarray,
        cfg: dict,
        seed: int,
        x_coords: np.ndarray,
        z_coords: np.ndarray,
        cell_size: float
) -> np.ndarray:
    """
    Применяет эффект террасирования, создавая "полки" и "обрывы"
    путем контролируемой деформации.
    """
    # 1. Получаем параметры из JSON
    terrace_height = float(cfg.get("step_height_m", 50.0))
    ledge_ratio = float(cfg.get("ledge_ratio", 0.8))
    strength_m = float(cfg.get("strength_m", 15.0))

    # 2. Генерируем "ломающий" шум
    noise_cfg = cfg.get("noise", {})
    breaking_noise = generate_noise_layer(
        seed + 101, noise_cfg, x_coords, z_coords, cell_size
    )

    # 3. Применяем деформацию
    ledge_point = terrace_height * ledge_ratio
    out_grid = height_grid.copy()

    for z in range(height_grid.shape[0]):
        for x in range(height_grid.shape[1]):
            mask_strength = mountain_mask[z, x]
            if mask_strength < 0.1:
                continue

            h = height_grid[z, x]
            step_pos = h % terrace_height

            # --- Простая и предсказуемая деформация ---
            deformation = 0.0
            if step_pos < ledge_point:
                # На "полке": плавно выдавливаем наружу
                t = (step_pos / ledge_point) * 2.0 - 1.0  # Диапазон [-1, 1]
                deformation = (1.0 - t * t) * strength_m
            else:
                # На "обрыве": ничего не делаем (оставляем исходный склон)
                pass

            # Применяем деформацию с учетом "ломающего" шума и маски гор
            out_grid[z, x] += deformation * breaking_noise[z, x] * mask_strength

    return out_grid