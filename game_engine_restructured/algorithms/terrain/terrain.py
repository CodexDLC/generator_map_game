# ==============================================================================
# Файл: game_engine_restructured/algorithms/terrain/terrain.py
# ВЕРСИЯ 4.5: Восстановлена полная функциональность slope_limiter и
#              подробные диагностические логи.
# ==============================================================================
from __future__ import annotations
import math
from typing import Any, Dict
import numpy as np

from .terrain_helpers import generate_noise_layer
from ...numerics.masking import create_mask
from ...numerics.slope import apply_slope_limiter


def _print_range(tag: str, arr: np.ndarray) -> None:
    """Выводит в консоль мин/макс/диапазон для numpy-массива."""
    if arr.size == 0:
        print(f"[DIAGNOSTIC] {tag}: (пустой массив)")
        return
    mn, mx = float(np.min(arr)), float(np.max(arr))
    print(f"  -> [DIAGNOSTIC] Диапазон '{tag}': min={mn:<8.2f} max={mx:<8.2f} delta={mx - mn:.2f}")


def apply_modulated_layers(
        base_layer: np.ndarray,
        preset: Any,
        seed: int,
        x_coords: np.ndarray,
        z_coords: np.ndarray,
        cell_size: float
) -> np.ndarray:
    spectral_cfg = getattr(preset, "elevation", {}).get("spectral", {})
    masks_cfg = spectral_cfg.get("masks", {})
    continents_cfg = spectral_cfg.get("continents", {})

    continents_amp = float(continents_cfg.get("amp_m", 1.0))
    if continents_amp == 0: return np.zeros_like(base_layer)
    base_layer_norm = base_layer / continents_amp

    total_added_height = np.zeros_like(base_layer)
    layer_seed = seed + 1

    for mask_name, mask_config in masks_cfg.items():
        mask_creation_params = {
            "threshold": mask_config.get("threshold", 0.5),
            "invert": mask_config.get("invert", False),
            "fade_range": mask_config.get("fade_range", 0.1)
        }
        mask = create_mask(base_layer_norm, **mask_creation_params)

        if "layers" in mask_config:
            mask_contribution = np.zeros_like(base_layer)

            for layer_name, layer_cfg in mask_config["layers"].items():
                sub_layer = generate_noise_layer(
                    layer_seed, layer_cfg, x_coords, z_coords, cell_size
                )
                mask_contribution += sub_layer
                layer_seed += 1

            total_added_height += mask_contribution * mask

    return total_added_height


def generate_elevation_region(
        seed: int, scx: int, scz: int, region_size_chunks: int, chunk_size: int, preset: Any, scratch_buffers: dict,
) -> np.ndarray:
    cfg = getattr(preset, "elevation", {})
    spectral_cfg = cfg.get("spectral", {})
    cell_size = float(getattr(preset, "cell_size", 1.0))
    ext_size = (region_size_chunks + 2) * chunk_size
    base_cx = scx * region_size_chunks - 1
    base_cz = scz * region_size_chunks - 1
    gx0_px = base_cx * chunk_size
    gz0_px = base_cz * chunk_size

    px_coords_x = np.arange(ext_size, dtype=np.float64) + gx0_px
    px_coords_z = np.arange(ext_size, dtype=np.float64) + gz0_px
    x_coords_base, z_coords_base = np.meshgrid(px_coords_x, px_coords_z)

    print("  -> [Terrain] Генерация базового слоя 'continents'...")
    continents_layer = generate_noise_layer(
        seed, spectral_cfg["continents"], x_coords_base, z_coords_base, cell_size
    )
    _print_range("Continents Layer", continents_layer)

    added_layers = apply_modulated_layers(
        continents_layer, preset, seed, x_coords_base, z_coords_base, cell_size
    )
    _print_range("Added Detail Layers", added_layers)

    height_grid = continents_layer + added_layers

    height_grid += float(cfg.get("base_height_m", 0.0))
    _print_range("Before Clip", height_grid)  # Дополнительный лог до срезания

    np.clip(height_grid, -float('inf'), float(cfg.get("max_height_m", 1400.0)), out=height_grid)
    _print_range("After Clip", height_grid)  # Дополнительный лог после срезания

    # --- ВОССТАНОВЛЕННЫЙ И ПОЛНЫЙ КОД ---
    if cfg.get("use_slope_limiter", False):
        print("  -> [Terrain] Применение ограничителя крутизны склонов...")
        slope_angle = float(cfg.get("slope_limiter_angle_deg", 75.0))
        max_slope_tangent = math.tan(math.radians(slope_angle))
        iters = int(cfg.get("slope_limiter_iterations", 4))
        apply_slope_limiter(height_grid, max_slope_tangent, cell_size, iters)
    # --- КОНЕЦ ---

    _print_range("Final Height Grid", height_grid)
    return height_grid.copy()