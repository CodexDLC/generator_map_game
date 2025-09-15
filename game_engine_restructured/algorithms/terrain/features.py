# ==============================================================================
# Файл: game_engine_restructured/algorithms/terrain/terrain_features.py
# Назначение: Архив сложных и экспериментальных функций для генерации
#              продвинутых особенностей ландшафта (каньоны, плато).
#              Этот код не используется в основном пайплайне, но может быть
#              подключен для создания уникальных биомов.
# ==============================================================================

from __future__ import annotations
from typing import Any, Dict
import numpy as np
from scipy.ndimage import gaussian_filter

from ...core.noise.fast_noise import fbm_grid_warped
from .terrain import  _generate_layer
from .slope import compute_slope_mask


# ==============================================================================
# --- ФИШКА 1: Создание "Меса"-ландшафта (плато) ---
# ==============================================================================

def apply_mesa_plateau_feature(
        height_grid: np.ndarray,
        seed: int,
        cfg: Dict,
        spectral_cfg: Dict,
        coords: Dict[str, np.ndarray],
        cell_size: float,
        scratch_buffers: dict
) -> np.ndarray:
    """
    Применяет "срезание" вершин для создания плато и добавляет шум на их поверхность.
    """
    # Шаг 1: Clip/normalization для плато
    max_clip = float(cfg.get("plateau_clip_height_m", 50.0))
    h_grid = np.clip(height_grid, 0.0, max_clip)
    plateau_fraction = np.mean(h_grid >= max_clip - 0.1)
    print(f"[FEATURE] Clipped to plateau {max_clip}m: fraction={plateau_fraction:.3f}")

    # Шаг 2: Шум на вершинах плато
    upper_noise_cfg = spectral_cfg.get("plateau_upper_noise", {})
    if upper_noise_cfg.get("enabled", True):
        plateau_mask = (h_grid >= max_clip - 0.1).astype(np.float32)
        upper_noise = _generate_layer(
            seed + 3, upper_noise_cfg,
            coords["x"], coords["z"],
            cell_size, scratch_buffers["a"]
        )
        h_grid += upper_noise * plateau_mask

    # Шаг 3: Финальная нормализация
    final_max = float(cfg.get("final_max_height_m", 100.0))
    current_max = np.max(h_grid)
    if current_max > 0:
        h_grid = (h_grid / current_max) * final_max

    return h_grid


# ==============================================================================
# --- ФИШКА 2: Эрозия обрывов для создания скалистых краев ---
# ==============================================================================

def apply_cliff_erosion_feature(
        height_grid: np.ndarray,
        seed: int,
        cliff_cfg: Dict,
        coords: Dict[str, np.ndarray],
        cell_size: float,
        scratch_buffers: dict
) -> np.ndarray:
    """
    Находит крутые склоны и применяет к ним "разъедающий" шум эрозии.
    """
    print("  -> [FEATURE] Eroding cliffs...")
    # 1. Находим края плато (крутые склоны)
    slope_mask = compute_slope_mask(
        height_grid, cell_size,
        angle_threshold_deg=float(cliff_cfg.get("slope_angle_deg", 20.0)),
        band_cells=int(cliff_cfg.get("band_cells", 5))
    ).astype(np.float32)

    # 2. Создаем "рампы" - участки, где эрозия будет слабее
    ramp_cfg = cliff_cfg.get("ramps", {})
    ramp_noise = _generate_layer(
        seed ^ 0xC0FE, ramp_cfg,
        coords["x"], coords["z"],
        cell_size, scratch_buffers["a"]
    )
    # Рампы там, где шум > 40% от его амплитуды
    ramp_mask = (np.abs(ramp_noise) > ramp_cfg.get("amp_m", 1.0) * 0.4).astype(np.float32)

    # 3. Применяем эрозию, ослабляя ее на рампах
    erosion_noise = _generate_layer(
        seed + 777, cliff_cfg,
        coords["x"], coords["z"],
        cell_size, scratch_buffers["a"]
    )

    # Умножаем маску склонов на "маску мягкости" рамп
    erosion_strength = slope_mask * (1.0 - ramp_mask * float(ramp_cfg.get("softness", 0.8)))

    return height_grid + (erosion_noise * erosion_strength)