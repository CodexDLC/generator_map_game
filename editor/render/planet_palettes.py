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

# --- НОВЫЙ БЛОК: Цвета для биомов на глобальной карте ---
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
    # Просто преобразуем значение высоты [0,1] в цвет [0,255]
    gray_values = (z * 255).astype(np.uint8)
    # Создаем массив RGB, где все три канала равны gray_values
    return np.stack([gray_values, gray_values, gray_values], axis=-1) / 255.0

def map_planet_climate_palette(dominant_biomes: List[str]) -> np.ndarray:
    """ Раскрашивает планету по доминирующему биому для каждой вершины. """
    colors = np.array([BIOME_COLORS.get(biome_id, BIOME_COLORS["default"]) for biome_id in dominant_biomes], dtype=np.uint8)
    return colors / 255.0 # Возвращаем в формате float [0,1]

