import numpy as np
from opensimplex import OpenSimplex
from setting.config import BiomeConfig
from setting.constants import *


def biome_block(height01, seed: int, gx0: int, gy0: int,
                land_height_m: float, meters_per_pixel: float,
                biome_config: BiomeConfig,
                moisture_scale: float = 4000.0, octaves: int = 4):
    h, w = height01.shape
    gen_m = OpenSimplex(seed ^ 0xA5A5A5A5)
    inv_m = 1.0 / max(moisture_scale, 1e-6)
    moisture = np.zeros_like(height01, dtype=np.float32)
    for j in range(h):
        yy = (gy0 + j) * inv_m
        row = moisture[j]
        for i in range(w):
            xx = (gx0 + i) * inv_m
            v = 0.0
            amp = 1.0
            lac = 2.0
            gain = 0.5
            freq = 1.0
            for _ in range(octaves):
                v += amp * gen_m.noise2(xx * freq, yy * freq)
                freq *= lac
                amp *= gain
            row[i] = 0.5 * (v / (1.0 - gain) + 1.0)

    height_in_m = height01 * land_height_m
    gy, gx = np.gradient(height_in_m, meters_per_pixel, meters_per_pixel)
    slope = np.degrees(np.arctan(np.hypot(gx, gy)))

    # --- НОВАЯ УПРОЩЕННАЯ ЛОГИКА С ПРАВИЛЬНЫМИ ПРИОРИТЕТАМИ ---

    # 1. Начинаем с базового слоя: вся суша - это равнины или леса.
    biome = np.full((h, w), BIOME_ID_PLAIN, dtype=np.uint8)
    biome[moisture >= MOISTURE_THRESHOLD_FOREST] = BIOME_ID_FOREST

    # 2. Добавляем пляжи. Они перекрывают равнины/леса на низкой высоте.
    is_beach_height = height_in_m < biome_config.beach_height_m
    biome[is_beach_height] = BIOME_ID_BEACH

    # 3. Добавляем снег. Он перекрывает всё на большой высоте.
    is_snow_height = height_in_m >= biome_config.snow_height_m
    biome[is_snow_height] = BIOME_ID_SNOW

    # 4. Добавляем скалы. У них высокий приоритет, они перекрывают и траву, и снег на крутых склонах.
    is_rock_slope = slope > biome_config.max_grass_slope_deg
    biome[is_rock_slope] = BIOME_ID_ROCK

    # 5. Добавляем воду. У нее самый высокий приоритет, она перекрывает всё остальное.
    is_ocean = height_in_m < biome_config.ocean_level_m
    biome[is_ocean] = BIOME_ID_WATER_VISUAL

    return biome


def biome_palette():
    import numpy as np
    palette = np.zeros((100, 3), dtype=np.uint8)
    palette[BIOME_ID_LAND_BASE] = [139, 69, 19]
    palette[BIOME_ID_ROCK] = [130, 130, 130]
    palette[BIOME_ID_BEACH] = [240, 220, 170]
    palette[BIOME_ID_PLAIN] = [95, 180, 60]
    palette[BIOME_ID_FOREST] = [20, 110, 30]
    palette[BIOME_ID_SNOW] = [240, 240, 240]
    palette[BIOME_ID_WATER_VISUAL] = [10, 40, 120]
    return palette