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
from ...numerics.new_test import anti_ripple
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
        base_layer_for_masks: np.ndarray,
        preset: Any,
        seed: int,
        x_coords: np.ndarray,
        z_coords: np.ndarray,
        cell_size: float
) -> np.ndarray:
    import numpy as np

    def _morph_wave_ridge(n: np.ndarray, k: np.ndarray, sharpness_enhance: float = 0.0) -> np.ndarray:
        n = np.clip(n, -1.0, 1.0).astype(np.float32)
        k = np.clip(k, -1.0, 1.0).astype(np.float32)
        t_r = np.maximum(0.0, k)      # ridge доля
        t_b = np.maximum(0.0, -k)     # billow доля
        b = 2.0 * np.abs(n) - 1.0     # billow ∈ [-1,1]
        r = 1.0 - 2.0 * np.abs(n)     # ridge  ∈ [-1,1]
        out = n * (1.0 - t_r - t_b) + r * t_r + b * t_b
        if sharpness_enhance > 0.0:
            s = 1.0 + float(sharpness_enhance)
            out = np.sign(out) * (np.abs(out) ** s)
        return np.clip(out, -1.0, 1.0).astype(np.float32)

    spectral_cfg = getattr(preset, "elevation", {}).get("spectral", {})
    masks_cfg = spectral_cfg.get("masks", {})

    total_added_height = np.zeros_like(base_layer_for_masks, dtype=np.float32)
    layer_seed = seed + 1

    # вес считаем только от "сырой" основы
    base_norm_raw_global = np.clip(
        np.nan_to_num(base_layer_for_masks, nan=0.0, posinf=1.0, neginf=0.0),
        0.0, 1.0
    ).astype(np.float32)

    for mask_name, mask_config in masks_cfg.items():
        # A) локальная норма для формы этой маски
        norm_for_mask = base_norm_raw_global.copy()

        # B) MORPH формы (опционально)
        morph_cfg = mask_config.get("morph", {})
        if morph_cfg.get("enabled", False):
            n_signed = 2.0 * norm_for_mask - 1.0
            k_scale_tiles = float(morph_cfg.get("scale_tiles", 10000.0))
            k_amp         = float(morph_cfg.get("amp", 0.8))
            k_seed_off    = int(morph_cfg.get("seed_offset", 777))
            sharp_enh     = float(morph_cfg.get("sharpness_enhance", 0.5))
            slope_er      = float(morph_cfg.get("slope_erosion", 0.4))
            alt_er        = float(morph_cfg.get("altitude_erosion", 0.4))
            ridge_er      = float(morph_cfg.get("ridge_erosion", 0.2))

            period_m = max(1e-6, k_scale_tiles)     # координаты уже в метрах
            k_freq = 1.0 / period_m
            try:
                import fast_noise
                k = k_amp * fast_noise.simplex2d_grid(x_coords, z_coords, seed + k_seed_off, k_freq)
            except Exception:
                k = n_signed.copy()
                for _ in range(3):
                    k = (np.roll(k, 1, 0) + k + np.roll(k, -1, 0) +
                         np.roll(k, 1, 1) + np.roll(k, -1, 1)) / 5.0
                k *= k_amp
            k = np.clip(k, -1.0, 1.0).astype(np.float32)

            n_m = _morph_wave_ridge(n_signed, k, sharpness_enhance=sharp_enh)

            if slope_er > 0.0:
                dx = (np.roll(n_m, -1, 1) - np.roll(n_m, 1, 1)) / (2.0 * float(cell_size))
                dz = (np.roll(n_m, -1, 0) - np.roll(n_m, 1, 0)) / (2.0 * float(cell_size))
                slope = np.sqrt(dx * dx + dz * dz)
                n_m *= 1.0 / (1.0 + (slope_er * slope) ** 2)

            if alt_er > 0.0:
                h_loc = 0.5 * (n_m + 1.0)
                n_m *= (1.0 - alt_er * h_loc)

            if ridge_er > 0.0:
                ridge_mask = np.clip(1.0 - np.abs(n_m), 0.0, 1.0)
                n_m *= (1.0 - ridge_er * ridge_mask)

            norm_for_mask = np.clip(0.5 * (n_m + 1.0), 0.0, 1.0)

        # C) базовая (пороговая) маска — для mountains дополнительно спасаем вершины
        mask_creation_params = {
            "threshold": mask_config.get("threshold", 0.5),
            "invert": mask_config.get("invert", False),
            "fade_range": mask_config.get("fade_range", 0.1)
        }

        if mask_name == "mountains":
            # параметры смешивания можно задавать в morph, иначе дефолты
            t_raw    = float(morph_cfg.get("raw_blend", 0.5))   # 50% RAW + 50% MORPH
            max_drop = float(morph_cfg.get("max_drop", 0.08))   # максимум, на сколько морф может уронить RAW

            # 1) смесь RAW+MORPH и защита верха
            mixed = (1.0 - t_raw) * norm_for_mask + t_raw * base_norm_raw_global
            norm_for_mask = np.maximum(mixed, base_norm_raw_global - max_drop)

            # 2) маска через двойной smoothstep-гейт: включение по RAW, форма по MORPH
            th   = float(mask_creation_params["threshold"])
            fade = float(mask_creation_params["fade_range"])
            eps  = max(1e-6, 0.5 * fade)

            raw_gate = np.clip((base_norm_raw_global - th) / eps, 0.0, 1.0)
            mrf_gate = np.clip((norm_for_mask        - th) / eps, 0.0, 1.0)
            raw_gate = raw_gate * raw_gate * (3.0 - 2.0 * raw_gate)
            mrf_gate = mrf_gate * mrf_gate * (3.0 - 2.0 * mrf_gate)

            base_mask = raw_gate * mrf_gate

            # диагностика до весов
            p_raw = float(np.mean(base_norm_raw_global > th) * 100.0)
            p_mrf = float(np.mean(norm_for_mask        > th) * 100.0)
            print(f"[MASKDBG] mountains: >{th:.2f} raw={p_raw:.1f}% morph_mix={p_mrf:.1f}% | "
                  f"raw_range=({base_norm_raw_global.min():.2f},{base_norm_raw_global.max():.2f}) | "
                  f"morph_range=({norm_for_mask.min():.2f},{norm_for_mask.max():.2f}) | "
                  f"base_mask=({base_mask.min():.2f},{base_mask.max():.2f})")
        else:
            base_mask = create_mask(norm_for_mask, **mask_creation_params)

        # D) непрерывная модуляция по высоте (вес) — ОТ RAW (не от морфа)
        mod_cfg = mask_config.get("modulate", None)
        if mod_cfg:
            mode = mod_cfg.get("mode", "none")
            gamma = float(mod_cfg.get("gamma", 1.0))
            if gamma <= 0.0:
                gamma = 1.0

            if mode == "high":
                weight = np.power(base_norm_raw_global, gamma)
                mask = np.clip(base_mask * weight, 0.0, 1.0)
            elif mode == "low":
                weight = np.power(1.0 - base_norm_raw_global, gamma)
                mask = np.clip(base_mask * weight, 0.0, 1.0)
            else:
                mask = base_mask
        else:
            mask = base_mask

        if mask_name == "mountains":
            print(f"[MASKDBG] mountains: final mask=({mask.min():.2f},{mask.max():.2f})")

        # E) суммируем слои
        if "layers" in mask_config:
            mask_contribution = np.zeros_like(total_added_height, dtype=np.float32)
            for layer_name, layer_cfg in mask_config["layers"].items():
                sub_layer = generate_noise_layer(
                    layer_seed, layer_cfg, x_coords, z_coords, cell_size
                ).astype(np.float32)
                print(f"[DIAG] {mask_name}.{layer_name}: amp={layer_cfg.get('amp_m', 0)} "
                      f"range=({float(np.min(sub_layer)):.2f},{float(np.max(sub_layer)):.2f})")
                mask_contribution += sub_layer
                layer_seed += 1

            masked = (mask_contribution * mask).astype(np.float32)
            total_added_height += masked

            print(f"[DIAG] {mask_name}: pre=({float(np.min(mask_contribution)):.2f},"
                  f"{float(np.max(mask_contribution)):.2f}) "
                  f"weight=({float(np.min(mask)):.2f},{float(np.max(mask)):.2f}) "
                  f"post=({float(np.min(masked)):.2f},{float(np.max(masked)):.2f})")

    return total_added_height.astype(np.float32)




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

    height_grid = anti_ripple(height_grid, cell_size,
                              sigma_low=9.0, sigma_high=3.5,
                              alpha=0.55, slope_deg_mid=22.0, slope_deg_hard=38.0)
    _print_range("After Anti-Ripple", height_grid)

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