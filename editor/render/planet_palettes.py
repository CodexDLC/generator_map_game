# editor/render/planet_palettes.py
from __future__ import annotations
from typing import List, Tuple
import numpy as np

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

def map_planet_height_palette(z01: np.ndarray) -> np.ndarray:
    """ Раскрашивает планету по высоте в Grayscale. """
    z = np.clip(z01, 0.0, 1.0)
    gray_values = (z * 255).astype(np.uint8)
    return np.stack([gray_values, gray_values, gray_values], axis=-1) / 255.0

# --- НАЧАЛО ИЗМЕНЕНИЙ: НОВАЯ ФУНКЦИЯ ДЛЯ ОТРИСОВКИ ВОДЫ И СУШИ ---
def map_planet_bimodal_palette(
    z01: np.ndarray,
    sea_level_01: float,
    dominant_biomes_on_land: List[str]
) -> np.ndarray:
    """
    Раскрашивает планету: всё что ниже sea_level_01 - вода, всё что выше - по биомам.
    """
    colors = np.zeros((len(z01), 3), dtype=np.float32)
    is_land_mask = z01 >= sea_level_01

    # --- Шаг 1: Раскрашиваем воду ---
    is_water_mask = ~is_land_mask
    if np.any(is_water_mask):
        # Нормализуем глубину от 0 (поверхность) до 1 (самое дно)
        water_depth_norm = z01[is_water_mask] / max(sea_level_01, 1e-6)
        # Простая линейная интерполяция между двумя цветами воды
        deep_color = np.array(REGION_PALETTES["_Water"][0][1]) / 255.0
        shallow_color = np.array(REGION_PALETTES["_Water"][1][1]) / 255.0
        # lerp(deep, shallow, depth)
        colors[is_water_mask] = deep_color * (1.0 - water_depth_norm[:, np.newaxis]) + shallow_color * water_depth_norm[:, np.newaxis]

    # --- Шаг 2: Раскрашиваем сушу ---
    if np.any(is_land_mask) and dominant_biomes_on_land:
        land_colors = np.array([BIOME_COLORS.get(biome_id, BIOME_COLORS["default"]) for biome_id in dominant_biomes_on_land], dtype=np.uint8)
        colors[is_land_mask] = land_colors / 255.0

    return colors
# --- КОНЕЦ ИЗМЕНЕНИЙ ---

def map_planet_climate_palette(dominant_biomes: List[str]) -> np.ndarray:
    """ Раскрашивает планету по доминирующему биому для каждой вершины. """
    colors = np.array([BIOME_COLORS.get(biome_id, BIOME_COLORS["default"]) for biome_id in dominant_biomes], dtype=np.uint8)
    return colors / 255.0