# editor/render/palettes.py
from __future__ import annotations
from typing import List, Tuple, Optional
import numpy as np
import logging
from vispy.color import Colormap

logger = logging.getLogger(__name__)

# =============================================================================
# === ОБЪЕДИНЕННЫЕ ПАЛИТРЫ ===
# =============================================================================

# Палитры для ландшафта (суши)
LAND_PALETTES: dict[str, List[Tuple[float, Tuple[int, int, int]]]] = {
    "Rock": [
        (0.00, (40, 40, 44)),
        (0.35, (90, 90, 98)),
        (0.65, (160, 160, 170)),
        (0.90, (215, 215, 220)),
        (1.00, (245, 245, 250)),
    ],
    "Desert": [
        (0.00, (60, 38, 23)),
        (0.30, (120, 78, 38)),
        (0.60, (189, 151, 79)),
        (0.85, (230, 205, 140)),
        (1.00, (250, 240, 210)),
    ],
    "Snow": [
        (0.00, (80, 80, 90)),
        (0.40, (150, 150, 165)),
        (0.75, (225, 225, 235)),
        (1.00, (255, 255, 255)),
    ],
    "Volcano": [
        (0.00, (20, 18, 18)),
        (0.40, (70, 55, 45)),
        (0.70, (120, 95, 65)),
        (0.90, (170, 150, 120)),
        (1.00, (225, 215, 200)),
    ],
    # Палитра для воды
    "_Water": [
        (0.0, (10, 20, 60)),  # Глубокий океан
        (1.0, (40, 80, 150)),  # Мелководье
    ]
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


# =============================================================================
# === ОБЪЕДИНЕННЫЕ ФУНКЦИИ-МАППЕРЫ ===
# =============================================================================

def make_colormap_from_palette(name: str) -> Colormap:
    """
    (Перенесено из render_palettes.py)
    Создает Colormap из vispy по имени палитры.
    """
    stops = LAND_PALETTES.get(name) or LAND_PALETTES["Rock"]
    pos = [p for p, _ in stops]
    rgb = [[c / 255.0 for c in col] for _, col in stops]
    return Colormap(rgb, controls=pos)


def map_palette_cpu(
        z01: np.ndarray,
        name: str,
        sea_level_pct: Optional[float] = None
) -> np.ndarray:
    """
    (Перенесено из render_palettes.py)
    Перевод нормализованных высот z∈[0,1] в RGB для 3D-превью РЕГИОНА.
    Если sea_level_pct задан, все что ниже - красится в цвет воды.
    """
    z = np.clip(z01, 0.0, 1.0).astype(np.float32, copy=False)
    rgb = np.zeros((*z.shape, 3), dtype=np.float32)
    is_land = np.ones_like(z, dtype=bool)

    # 1. Раскрашиваем воду, если нужно
    if sea_level_pct is not None and sea_level_pct > 0.0:
        is_water = z < sea_level_pct
        is_land = ~is_water

        if np.any(is_water):
            water_depth_norm = z[is_water] / sea_level_pct
            # ИСПОЛЬЗУЕМ ОБЩУЮ ПАЛИТРУ
            stops_water = LAND_PALETTES["_Water"]
            xs_water = np.array([p for p, _ in stops_water], dtype=np.float32)
            cols_water = np.array([[r, g, b] for _, (r, g, b) in stops_water], dtype=np.float32) / 255.0

            idx_w = np.searchsorted(xs_water, water_depth_norm, side="right")
            idx0_w, idx1_w = np.clip(idx_w - 1, 0, len(xs_water) - 1), np.clip(idx_w, 0, len(xs_water) - 1)
            x0_w, x1_w = xs_water[idx0_w], xs_water[idx1_w]
            c0_w, c1_w = cols_water[idx0_w], cols_water[idx1_w]
            denom_w = np.maximum(x1_w - x0_w, 1e-6)
            t_w = (water_depth_norm - x0_w) / denom_w

            rgb[is_water] = c0_w * (1.0 - t_w)[..., None] + c1_w * t_w[..., None]

    # 2. Раскрашиваем сушу
    if np.any(is_land):
        if sea_level_pct is not None and (1.0 - sea_level_pct) > 1e-6:
            land_height_norm = (z[is_land] - sea_level_pct) / (1.0 - sea_level_pct)
        else:
            land_height_norm = z[is_land]

        # ИСПОЛЬЗУЕМ ОБЩУЮ ПАЛИТРУ
        stops_land = LAND_PALETTES.get(name) or LAND_PALETTES["Rock"]
        xs_land = np.array([p for p, _ in stops_land], dtype=np.float32)
        cols_land = np.array([[r, g, b] for _, (r, g, b) in stops_land], dtype=np.float32) / 255.0

        idx = np.searchsorted(xs_land, land_height_norm, side="right")
        idx0, idx1 = np.clip(idx - 1, 0, len(xs_land) - 1), np.clip(idx, 0, len(xs_land) - 1)
        x0, x1 = xs_land[idx0], xs_land[idx1]
        c0, c1 = cols_land[idx0], cols_land[idx1]
        denom = np.maximum(x1 - x0, 1e-6)
        t = (land_height_norm - x0) / denom

        rgb[is_land] = c0 * (1.0 - t)[..., None] + c1 * t[..., None]

    return np.clip(rgb, 0.0, 1.0)


# --- НОВОЕ ИМЯ ФУНКЦИИ ---
def map_height_to_grayscale(z01: np.ndarray) -> np.ndarray:
    """
    (Перенесено из planet_palettes.py, ПЕРЕИМЕНОВАНО)
    Раскрашивает карту высот в Grayscale.
    """
    z = np.clip(z01, 0.0, 1.0)
    gray_values = (z * 255).astype(np.uint8)
    return (np.stack([gray_values, gray_values, gray_values], axis=-1) / 255.0).astype(np.float32)


def map_planet_bimodal_palette(
    z01: np.ndarray,
    sea_level_01: float,
    dominant_biomes_for_render: List[str]
) -> np.ndarray:
    """
    (Перенесено из planet_palettes.py)
    Раскрашивает планету: всё что ниже sea_level_01 - вода, всё что выше - по биомам.
    """
    # Маски для суши и воды
    is_land_mask = z01 >= sea_level_01
    is_water_mask = ~is_land_mask

    # --- Шаг 1: Рассчитываем цвета для ВСЕХ точек, как если бы они были ВОДОЙ ---
    water_depth_norm = np.clip(z01 / max(sea_level_01, 1e-6), 0.0, 1.0)
    # ИСПОЛЬЗУЕМ ОБЩУЮ ПАЛИТРУ
    deep_color = np.array(LAND_PALETTES["_Water"][0][1]) / 255.0
    shallow_color = np.array(LAND_PALETTES["_Water"][1][1]) / 255.0
    water_colors = deep_color * (1.0 - water_depth_norm[:, np.newaxis]) + shallow_color * water_depth_norm[:, np.newaxis]

    # --- Шаг 2: Рассчитываем цвета для ВСЕХ точек, как если бы они были СУШЕЙ ---
    land_colors = np.zeros_like(water_colors)
    if dominant_biomes_for_render:
        # Убедимся, что dominant_biomes_for_render имеет правильную длину
        if len(dominant_biomes_for_render) == len(land_colors):
            # ИСПОЛЬЗУЕМ ОБЩУЮ ПАЛИТРУ
            all_biome_colors = np.array([BIOME_COLORS.get(biome_id, BIOME_COLORS["default"]) for biome_id in dominant_biomes_for_render], dtype=np.uint8) / 255.0
            land_colors = all_biome_colors
        else:
            logger.error(f"Размер массива биомов ({len(dominant_biomes_for_render)}) не совпадает с размером вершин ({len(land_colors)})!")

    # --- Шаг 3: Используем маску, чтобы выбрать цвет для каждой точки ---
    # np.where работает как тернарный оператор: (условие ? если_да : если_нет)
    final_colors = np.where(is_water_mask[:, np.newaxis], water_colors, land_colors)

    return final_colors.astype(np.float32)


def map_planet_climate_palette(dominant_biomes: List[str]) -> np.ndarray:
    """
    (Перенесено из planet_palettes.py)
    Раскрашивает планету по доминирующему биому для каждой вершины.
    """
    # ИСПОЛЬЗУЕМ ОБЩУЮ ПАЛИТРУ
    colors = np.array([BIOME_COLORS.get(biome_id, BIOME_COLORS["default"]) for biome_id in dominant_biomes], dtype=np.uint8)
    return colors / 255.0