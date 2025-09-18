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

    continents_amp = float(continents_cfg.get("amp_m", 1.0)) or 1.0
    base_layer_norm = np.clip(base_layer / continents_amp, 0.0, 1.0)  # y ∈ [0..1]

    total_added_height = np.zeros_like(base_layer)
    layer_seed = seed + 1

    for mask_name, mask_config in masks_cfg.items():
        # 1) базовая (пороговая) маска с fade
        mask_creation_params = {
            "threshold": mask_config.get("threshold", 0.5),
            "invert": mask_config.get("invert", False),
            "fade_range": mask_config.get("fade_range", 0.1)
        }
        base_mask = create_mask(base_layer_norm, **mask_creation_params)  # [0..1]

        # 2) НЕПРЕРЫВНАЯ модуляция по высоте (high/low) с гаммой
        mod_cfg = mask_config.get("modulate", None)
        if mod_cfg:
            mode = mod_cfg.get("mode", "none")  # "high" или "low"
            gamma = float(mod_cfg.get("gamma", 1.0))
            if gamma <= 0.0:
                gamma = 1.0
            if mode == "high":
                # горы: усиливать там, где континент высок (y^gamma)
                weight = np.power(base_layer_norm, gamma)
                mask = base_mask * weight
            elif mode == "low":
                # равнины: усиливать там, где континент низок ((1-y)^gamma)
                weight = np.power(1.0 - base_layer_norm, gamma)
                mask = base_mask * weight
            else:
                mask = base_mask
        else:
            mask = base_mask

        # 3) суммируем слои маски, потом применяем итоговый вес
        if "layers" in mask_config:
            mask_contribution = np.zeros_like(base_layer)

            for layer_name, layer_cfg in mask_config["layers"].items():
                sub_layer = generate_noise_layer(
                    layer_seed, layer_cfg, x_coords, z_coords, cell_size
                )

                r = bool(layer_cfg.get("ridge", False))
                ao = bool(layer_cfg.get("additive_only", False))
                mn, mx = float(np.min(sub_layer)), float(np.max(sub_layer))
                print(f"[DIAG] {mask_name}.{layer_name}: ridge={r} add_only={ao} amp={layer_cfg.get('amp_m',0)} range=({mn:.2f},{mx:.2f})")
                mask_contribution += sub_layer
                layer_seed += 1

            masked = mask_contribution * mask  # ← непрерывный вес применяется здесь
            total_added_height += masked


            pre_mn, pre_mx = float(np.min(mask_contribution)), float(np.max(mask_contribution))
            w_mn, w_mx = float(np.min(mask)), float(np.max(mask))
            post_mn, post_mx = float(np.min(masked)), float(np.max(masked))
            print(f"[DIAG] {mask_name}: pre=({pre_mn:.2f},{pre_mx:.2f}) weight=({w_mn:.2f},{w_mx:.2f}) post=({post_mn:.2f},{post_mx:.2f})")

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
    _print_range("Before Clip (no clip)", height_grid)

    ns_cfg = getattr(preset, "elevation", {}).get("non_slope_smoothing", {})
    if ns_cfg:
        # Маска «гор» из тех же настроек, что и при модуляции слоёв
        spectral_cfg = getattr(preset, "elevation", {}).get("spectral", {})
        continents_cfg = spectral_cfg.get("continents", {})
        continents_amp = float(continents_cfg.get("amp_m", 1.0)) or 1.0
        base_layer_norm = np.clip((continents_layer / continents_amp), 0.0, 1.0)

        masks_cfg = spectral_cfg.get("masks", {})
        m_cfg = masks_cfg.get("mountains", {})
        p_cfg = masks_cfg.get("plains", {})

        # маска гор/равнин — ровно как раньше (порог/инверт/фейд)
        from ...numerics.masking import create_mask
        mountain_mask = create_mask(
            base_layer_norm,
            threshold=float(m_cfg.get("threshold", 0.5)),
            invert=bool(m_cfg.get("invert", False)),
            fade_range=float(m_cfg.get("fade_range", 0.1)),
        )
        plains_mask = create_mask(
            base_layer_norm,
            threshold=float(p_cfg.get("threshold", 0.5)),
            invert=bool(p_cfg.get("invert", True)),
            fade_range=float(p_cfg.get("fade_range", 0.1)),
        )

        from .terrain_helpers import selective_smooth_non_slopes

        # конфиг «горы»
        ns_m = ns_cfg.get("mountains", {})
        if ns_m.get("enabled", False):
            height_grid = selective_smooth_non_slopes(
                height_grid,
                cell_size=cell_size,
                angle_deg=float(ns_m.get("angle_threshold_deg", 35.0)),
                margin_cells=int(ns_m.get("margin_cells", 3)),
                detail_keep=float(ns_m.get("detail_keep", 0.35)),
                blur_iters=int(ns_m.get("blur_iters", 1)),
                region_weight=mountain_mask,  # <— ТОЛЬКО на горной зоне (и только вне склонов)
            )
            _print_range("After Non-slope Smoothing (mountains)", height_grid)

        # конфиг «равнины» (если понадобится отдельно)
        ns_p = ns_cfg.get("plains", {})
        if ns_p.get("enabled", False):
            height_grid = selective_smooth_non_slopes(
                height_grid,
                cell_size=cell_size,
                angle_deg=float(ns_p.get("angle_threshold_deg", 30.0)),
                margin_cells=int(ns_p.get("margin_cells", 2)),
                detail_keep=float(ns_p.get("detail_keep", 0.5)),
                blur_iters=int(ns_p.get("blur_iters", 1)),
                region_weight=plains_mask,
            )
            _print_range("After Non-slope Smoothing (plains)", height_grid)


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