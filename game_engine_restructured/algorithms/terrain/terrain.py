# ==============================================================================
# Файл: game_engine_restructured/algorithms/terrain/terrain.py
# ВЕРСИЯ 5.0: Реализован композитный базовый слой по вашему алгоритму.
#              Логика создания континентов вынесена в отдельную функцию.
# ==============================================================================
from __future__ import annotations
import math
from typing import Any, Dict, Tuple
import numpy as np

from .terracing import apply_terracing_effect
from .terrain_helpers import generate_noise_layer, generate_base_noise, normalize_and_shape, scale_by_amplitude
from ...numerics.masking import create_mask
from ...numerics.slope import apply_slope_limiter


def _print_range(tag: str, arr: np.ndarray) -> None:
    """Выводит в консоль мин/макс/диапазон для numpy-массива."""
    if arr.size == 0:
        print(f"[DIAGNOSTIC] {tag}: (пустой массив)")
        return
    mn, mx = float(np.min(arr)), float(np.max(arr))
    print(f"  -> [DIAGNOSTIC] Диапазон '{tag}': min={mn:<8.2f} max={mx:<8.2f} delta={mx - mn:.2f}")


def _generate_composite_continents(
        seed: int,
        continents_cfg: Dict,
        x_coords: np.ndarray,
        z_coords: np.ndarray,
        cell_size: float
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Создает композитный базовый слой континентов по вашему алгоритму.
    Возвращает: (итоговый слой в метрах, "чистый" нормализованный шум для масок)
    """
    print("  -> [Terrain] Шаг 1: Генерация базового 'сырого' шума...")
    # Генерируем "сырой" FBM-шум один раз. Это наша общая основа.
    raw_continents_noise = generate_base_noise(
        seed, continents_cfg, x_coords, z_coords, cell_size
    )

    # --- ИСПРАВЛЕНИЕ: Создаем "чистый" шум для масок ДО применения shaping_power ---
    # Создаем временный конфиг без shaping_power, чтобы получить чистый шум
    clean_cfg_for_masks = continents_cfg.copy()
    clean_cfg_for_masks['shaping_power'] = 1.0
    normalized_clean_noise = normalize_and_shape(raw_continents_noise, clean_cfg_for_masks)

    print("  -> [Terrain] Шаг 2: Создание слоя 'Горы' (с shaping_power)...")
    # Создаем конфиг для гор, используя основной shaping_power
    mountain_specific_cfg = continents_cfg.copy()
    mountain_specific_cfg['shaping_power'] = float(continents_cfg.get("shaping_power", 1.5))
    # Применяем формирование к сырому шуму
    normalized_mountains = normalize_and_shape(raw_continents_noise, mountain_specific_cfg)
    # Масштабируем до высоты в метрах
    layer_a_mountains = scale_by_amplitude(normalized_mountains, continents_cfg)

    print("  -> [Terrain] Шаг 3: Создание слоя 'Равнины' (по настройкам plains_shaping)...")
    # Создаем конфиг для равнин. Начинаем с копии основного...
    plains_specific_cfg = continents_cfg.copy()
    # ...и читаем настройки из нового блока 'plains_shaping'
    plains_shaping_cfg = continents_cfg.get("plains_shaping", {"shaping_power": 1.0})
    plains_specific_cfg['shaping_power'] = float(plains_shaping_cfg.get("shaping_power", 1.0))
    # Применяем формирование (или не применяем, если power=1.0) к сырому шуму
    normalized_plains = normalize_and_shape(raw_continents_noise, plains_specific_cfg)
    # Масштабируем до высоты в метрах
    layer_b_plains = scale_by_amplitude(normalized_plains, continents_cfg)

    print("  -> [Terrain] Шаг 4: Создание масок для сшивания...")
    # Маски создаются на основе "чистого" шума, как и раньше
    mask_highlands = create_mask(
        base_noise=normalized_clean_noise,
        threshold=0.5,
        invert=False,
        fade_range=0.2
    )
    mask_lowlands = create_mask(
        base_noise=normalized_clean_noise,
        threshold=0.5,
        invert=True,
        fade_range=0.2
    )

    print("  -> [Terrain] Шаг 5: Сборка итогового композитного слоя...")
    composite_layer = (layer_a_mountains * mask_highlands) + (layer_b_plains * mask_lowlands)

    _print_range("Composite Continents", composite_layer)
    return composite_layer, normalized_clean_noise


def apply_modulated_layers(
        base_layer_for_masks: np.ndarray,  # <--- ИЗМЕНЕНИЕ: Теперь принимаем основу для масок
        preset: Any,
        seed: int,
        x_coords: np.ndarray,
        z_coords: np.ndarray,
        cell_size: float
) -> np.ndarray:
    spectral_cfg = getattr(preset, "elevation", {}).get("spectral", {})
    masks_cfg = spectral_cfg.get("masks", {})

    # --- ИЗМЕНЕНИЕ: Используем переданный "чистый" шум для создания масок ---
    base_layer_norm = base_layer_for_masks

    total_added_height = np.zeros_like(base_layer_for_masks)
    layer_seed = seed + 1

    for mask_name, mask_config in masks_cfg.items():
        # 1) базовая (пороговая) маска с fade
        mask_creation_params = {
            "threshold": mask_config.get("threshold", 0.5),
            "invert": mask_config.get("invert", False),
            "fade_range": mask_config.get("fade_range", 0.1)
        }
        base_mask = create_mask(base_layer_norm, **mask_creation_params)

        # 2) НЕПРЕРЫВНАЯ модуляция по высоте (high/low) с гаммой
        mod_cfg = mask_config.get("modulate", None)
        if mod_cfg:
            mode = mod_cfg.get("mode", "none")
            gamma = float(mod_cfg.get("gamma", 1.0))
            if gamma <= 0.0: gamma = 1.0

            if mode == "high":
                base_layer_norm = np.clip(np.nan_to_num(base_layer_for_masks, nan=0.0, posinf=1.0, neginf=0.0), 0.0,
                                          1.0)
                weight = np.power(base_layer_norm, gamma)
                mask = base_mask * weight
                mask = np.clip(mask, 0.0, 1.0)
            elif mode == "low":
                base_layer_norm = np.clip(np.nan_to_num(base_layer_for_masks, nan=0.0, posinf=1.0, neginf=0.0), 0.0,
                                          1.0)
                weight = np.power(1.0 - base_layer_norm, gamma)
                mask = base_mask * weight
                mask = np.clip(mask, 0.0, 1.0)
            else:
                mask = base_mask
        else:
            mask = base_mask

        # 3) суммируем слои маски, потом применяем итоговый вес
        if "layers" in mask_config:
            mask_contribution = np.zeros_like(total_added_height)
            for layer_name, layer_cfg in mask_config["layers"].items():
                sub_layer = generate_noise_layer(
                    layer_seed, layer_cfg, x_coords, z_coords, cell_size
                )
                print(
                    f"[DIAG] {mask_name}.{layer_name}: amp={layer_cfg.get('amp_m', 0)} range=({float(np.min(sub_layer)):.2f},{float(np.max(sub_layer)):.2f})")
                mask_contribution += sub_layer
                layer_seed += 1

            masked = mask_contribution * mask
            total_added_height += masked

            print(
                f"[DIAG] {mask_name}: pre=({float(np.min(mask_contribution)):.2f},{float(np.max(mask_contribution)):.2f}) weight=({float(np.min(mask)):.2f},{float(np.max(mask)):.2f}) post=({float(np.min(masked)):.2f},{float(np.max(masked)):.2f})")

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

    px_coords_x = np.arange(ext_size, dtype=np.float32) + gx0_px
    px_coords_z = np.arange(ext_size, dtype=np.float32) + gz0_px
    x_coords_base, z_coords_base = np.meshgrid(px_coords_x, px_coords_z)

    # --- ВЫЗОВ НОВОЙ ФУНКЦИИ ДЛЯ СОЗДАНИЯ БАЗЫ ---
    continents_layer, normalized_clean_noise_for_masks = _generate_composite_continents(
        seed=seed,
        continents_cfg=spectral_cfg["continents"],
        x_coords=x_coords_base,
        z_coords=z_coords_base,
        cell_size=cell_size
    )

    # --- ПРИМЕНЕНИЕ ДЕТАЛЬНЫХ СЛОЕВ ---
    print("  -> [Terrain] Шаг 6: Применение детальных слоев (горы, предгорья, равнины)...")
    added_layers = apply_modulated_layers(
        base_layer_for_masks=normalized_clean_noise_for_masks,  # <--- Передаем "чистый" шум для масок
        preset=preset,
        seed=seed,
        x_coords=x_coords_base,
        z_coords=z_coords_base,
        cell_size=cell_size
    )
    _print_range("Added Detail Layers", added_layers)

    # Собираем финальную карту высот
    height_grid = continents_layer + added_layers
    height_grid += float(cfg.get("base_height_m", 0.0))
    _print_range("After Details & Base Height", height_grid)

    # --- ПРИМЕНЕНИЕ ТЕРРАСИРОВАНИЯ И ДРУГИХ ЭФФЕКТОВ ---
    terracing_cfg = cfg.get("terracing", {})
    if terracing_cfg.get("enabled", False):
        print("  -> [Terrain] Применение террасирования...")
        current_min = np.min(height_grid)
        current_max = np.max(height_grid)
        final_height_norm = (height_grid - current_min) / (current_max - current_min + 1e-6)

        terracing_mask = create_mask(
            final_height_norm,
            threshold=terracing_cfg.get("mask_threshold", 0.6),
            invert=False,
            fade_range=terracing_cfg.get("mask_fade_range", 0.2)
        )

        height_grid = apply_terracing_effect(
            height_grid,
            terracing_mask,
            terracing_cfg,
            seed=seed,
            x_coords=x_coords_base,
            z_coords=z_coords_base,
            cell_size=cell_size
        )
        _print_range("After Terracing", height_grid)

    if cfg.get("use_slope_limiter", False):
        print("  -> [Terrain] Применение ограничителя крутизны склонов...")
        slope_angle = float(cfg.get("slope_limiter_angle_deg", 75.0))
        max_slope_tangent = math.tan(math.radians(slope_angle))
        iters = int(cfg.get("slope_limiter_iterations", 4))
        apply_slope_limiter(height_grid, max_slope_tangent, cell_size, iters)

    _print_range("Final Height Grid", height_grid)
    return height_grid.copy()