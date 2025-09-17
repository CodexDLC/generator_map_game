# Файл: game_engine_restructured/algorithms/terrain/terrain.py

from __future__ import annotations
import math
from typing import Any, Dict
import numpy as np

# --- ИМПОРТИРУЕМ НАШИ НОВЫЕ, ЧИСТЫЕ ИНСТРУМЕНТЫ ---
from .terrain_helpers import generate_noise_layer
from ...numerics.masking import create_mask  # <--- из нашего нового numerics/masking.py




# --- "Оркестратор" для сложной модуляции ---
def apply_advanced_modulation(
        layers: Dict[str, np.ndarray], preset: Any
) -> np.ndarray:
    """Применяет двухуровневую генерацию для Гор и Равнин."""
    print("[DIAGNOSTIC] Using 2-pipeline generation (Mountains/Plains).")

    spectral_cfg = getattr(preset, "elevation", {}).get("spectral", {})
    masks_cfg = spectral_cfg.get("masks", {})
    continents_cfg = spectral_cfg.get("continents", {})

    # Нормализуем базовый слой для создания масок
    continents_amp = float(continents_cfg.get("amp_m", 1.0))
    continents_norm = layers["continents"] / max(continents_amp, 1e-6)

    # Создаем маски
    mountain_mask = create_mask(continents_norm, **masks_cfg.get("mountains", {}))
    plains_mask = create_mask(continents_norm, **masks_cfg.get("plains", {}))

    # Собираем вклад от каждого конвейера
    mountain_contrib = (layers["mountain_features"] + layers["mountain_detail"]) * mountain_mask
    plains_contrib = (layers["plains_hills"] + layers["plains_detail"]) * plains_mask

    # Финальное сложение
    final_grid = layers["continents"] + mountain_contrib + plains_contrib + layers["micro_relief"]

    return final_grid


# --- Главный "Оркестратор" всего процесса ---
def generate_elevation_region(
        seed: int, scx: int, scz: int, region_size_chunks: int, chunk_size: int, preset: Any, scratch_buffers: dict,
) -> np.ndarray:
    # ... (код подготовки координат остается без изменений) ...

    # --- ЭТАП 1: Генерируем все слои по их именам из конфига ---
    spectral_cfg = cfg.get("spectral", {})
    generated_layers = {}
    layer_seed = seed

    for name, layer_cfg in spectral_cfg.items():
        if isinstance(layer_cfg, dict):  # Пропускаем "use_advanced_modulation", "masks" и т.д.
            print(f"[Generator] Creating layer: {name}")
            generated_layers[name] = generate_noise_layer(
                layer_seed, layer_cfg, x_coords_base, z_coords_base, cell_size
            )
            layer_seed += 1  # Увеличиваем сид для каждого слоя

    # --- ЭТАП 2: Смешиваем слои ---
    if spectral_cfg.get("use_advanced_modulation", False):
        height_grid = apply_advanced_modulation(generated_layers, preset)
    else:
        # Старый метод простого сложения (можно оставить для отладки)
        height_grid = sum(generated_layers.values())

    # --- ЭТАП 3: Финальные шаги (постобработка) ---
    # ... (код с base_height, clip и slope_limiter) ...

    return height_grid.copy()