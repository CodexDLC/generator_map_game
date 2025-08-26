import numpy as np
from opensimplex import OpenSimplex
from setting.config import BiomeConfig


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
            v = 0.0;
            amp = 1.0;
            lac = 2.0;
            gain = 0.5;
            freq = 1.0
            for _ in range(octaves):
                v += amp * gen_m.noise2(xx * freq, yy * freq)
                freq *= lac;
                amp *= gain
            row[i] = 0.5 * (v / (1 - 0.5) + 1.0)

    # Переводим высоту из диапазона 0..1 в метры
    height_in_m = (height01.astype(np.float32) / 65535.0) * land_height_m

    # --- НОВАЯ ЛОГИКА: Расчет угла наклона (градиента) ---
    height_map_m = (height01.astype(np.float32) / 65535.0) * land_height_m
    gy, gx = np.gradient(height_map_m, meters_per_pixel, meters_per_pixel)
    slope = np.degrees(np.arctan(np.hypot(gx, gy)))

    biome = np.zeros((h, w), dtype=np.uint8)

    # --- Этап 1: Определение базового рельефа ---

    # 0. Вода
    ocean_level_m_real = biome_config.ocean_level_m
    biome[height_in_m < ocean_level_m_real] = 0

    # 2. Скалы (определяются по углу наклона)
    biome[slope > biome_config.max_grass_slope_deg] = 2

    # 1. Суша (все, что не вода и не скалы)
    biome[(biome == 0) & (height_in_m >= ocean_level_m_real) & (slope <= biome_config.max_grass_slope_deg)] = 1

    # --- Этап 2: Наложение биомов на сушу ---

    # 3. Пляж (накладывается на сушу рядом с водой)
    mask_beach = (biome == 1) & (height_in_m >= ocean_level_m_real) & (height_in_m < biome_config.beach_height_m)
    biome[mask_beach] = 3

    # 4 и 5. Равнины и Леса (накладываются на оставшуюся сушу)
    rest_mask = (biome == 1)
    moist = moisture[rest_mask];
    tmp = np.zeros_like(moist, dtype=np.uint8)
    tmp[moist < 0.4] = 4;
    tmp[moist >= 0.4] = 5
    biome[rest_mask] = tmp

    # 6. Снег (накладывается на все, что выше определенной высоты)
    biome[height_in_m >= biome_config.snow_height_m] = 6

    return biome


def biome_palette():
    import numpy as np
    # Новая палитра: 0-Вода, 1-Суша(коричневый), 2-Скалы, 3-Пляж, 4-Равнина, 5-Лес, 6-Снег
    return np.array(
        [[10, 40, 120], [139, 69, 19], [130, 130, 130], [240, 220, 170], [95, 180, 60], [20, 110, 30], [240, 240, 240]],
        dtype=np.uint8)


def test():
    pass