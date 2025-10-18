# editor/render/planet_palettes.py
from __future__ import annotations
from typing import List, Tuple
import numpy as np
import logging  # <--- ДОБАВЛЕНО

# Палитры, предназначенные только для глобального вида планеты
# Палитры для 3D-превью РЕГИОНА
REGION_PALETTES: dict[str, List[Tuple[float, Tuple[int, int, int]]]] = {
    "Rock": [(0.0, (40, 40, 44)), (0.35, (90, 90, 98)), (0.65, (160, 160, 170)), (1.0, (245, 245, 250))],
    "Desert": [(0.0, (60, 38, 23)), (0.3, (120, 78, 38)), (0.6, (189, 151, 79)), (1.0, (250, 240, 210))],
    "Snow": [(0.0, (80, 80, 90)), (0.4, (150, 150, 165)), (0.75, (225, 225, 235)), (1.0, (255, 255, 255))],
    "_Water": [(0.0, (10, 20, 60)), (1.0, (40, 80, 150))]
}

# --- Цвета для биомов на глобальной карте ---
BIOME_COLORS: dict[str, Tuple[int, int, int]] = {
    "snow": (245, 245, 255),
    "tundra": (180, 190, 200),
    "taiga": (80, 110, 100),
    "grassland": (120, 160, 90),
    "temperate_deciduous_forest": (70, 140, 80),
    "temperate_desert": (210, 200, 150),
    "default": (128, 128, 128) # Серый цвет для ошибок или неопределенных биомов
}

# <--- ДОБАВЛЕНО
logger = logging.getLogger(__name__)

def map_planet_height_palette(z01: np.ndarray) -> np.ndarray:
    """ Раскрашивает планету по высоте в Grayscale. """
    z = np.clip(z01, 0.0, 1.0)
    gray_values = (z * 255).astype(np.uint8)
    return (np.stack([gray_values, gray_values, gray_values], axis=-1) / 255.0).astype(np.float32)


# --- ЗАМЕНА ВСЕЙ ФУНКЦИИ ---
def map_planet_bimodal_palette(
    z01: np.ndarray,
    sea_level_01: float,
    dominant_biomes_for_render: List[str]
) -> np.ndarray:
    """
    Раскрашивает планету: всё что ниже sea_level_01 - вода, всё что выше - по биомам.
    """
    # Маски для суши и воды
    is_land_mask = z01 >= sea_level_01
    is_water_mask = ~is_land_mask

    # --- Шаг 1: Рассчитываем цвета для ВСЕХ точек, как если бы они были ВОДОЙ ---
    water_depth_norm = np.clip(z01 / max(sea_level_01, 1e-6), 0.0, 1.0)
    deep_color = np.array(REGION_PALETTES["_Water"][0][1]) / 255.0
    shallow_color = np.array(REGION_PALETTES["_Water"][1][1]) / 255.0
    water_colors = deep_color * (1.0 - water_depth_norm[:, np.newaxis]) + shallow_color * water_depth_norm[:, np.newaxis]

    # --- Шаг 2: Рассчитываем цвета для ВСЕХ точек, как если бы они были СУШЕЙ ---
    land_colors = np.zeros_like(water_colors)
    if dominant_biomes_for_render:
        # Убедимся, что dominant_biomes_for_render имеет правильную длину
        if len(dominant_biomes_for_render) == len(land_colors):
            all_biome_colors = np.array([BIOME_COLORS.get(biome_id, BIOME_COLORS["default"]) for biome_id in dominant_biomes_for_render], dtype=np.uint8) / 255.0
            land_colors = all_biome_colors
        else:
            logger.error(f"Размер массива биомов ({len(dominant_biomes_for_render)}) не совпадает с размером вершин ({len(land_colors)})!")

    # --- Шаг 3: Используем маску, чтобы выбрать цвет для каждой точки ---
    # np.where работает как тернарный оператор: (условие ? если_да : если_нет)
    final_colors = np.where(is_water_mask[:, np.newaxis], water_colors, land_colors)

    return final_colors.astype(np.float32)


def map_planet_climate_palette(dominant_biomes: List[str]) -> np.ndarray:
    """ Раскрашивает планету по доминирующему биому для каждой вершины. """
    colors = np.array([BIOME_COLORS.get(biome_id, BIOME_COLORS["default"]) for biome_id in dominant_biomes], dtype=np.uint8)
    return colors / 255.0