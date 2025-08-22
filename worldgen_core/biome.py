import numpy as np
from opensimplex import OpenSimplex

def biome_block(height01, seed: int, gx0: int, gy0: int,
                ocean_level: float = 0.45, moisture_scale: float = 4000.0, octaves: int = 4):
    h, w = height01.shape
    gen_m = OpenSimplex(seed ^ 0xA5A5A5A5)
    inv_m = 1.0 / max(moisture_scale, 1e-6)
    moisture = np.zeros_like(height01, dtype=np.float32)
    for j in range(h):
        yy = (gy0 + j) * inv_m
        row = moisture[j]
        for i in range(w):
            xx = (gx0 + i) * inv_m
            v = 0.0; amp = 1.0; lac = 2.0; gain = 0.5; freq = 1.0
            for _ in range(octaves):
                v += amp * gen_m.noise2(xx * freq, yy * freq)
                freq *= lac; amp *= gain
            row[i] = 0.5 * (v / (1 - 0.5) + 1.0)

    beach_band, snow_level, rock_level = 0.02, 0.85, 0.70
    biome = np.zeros((h, w), dtype=np.uint8)
    biome[height01 < ocean_level] = 0
    mask_beach = (height01 >= ocean_level) & (height01 < ocean_level + beach_band); biome[mask_beach] = 1
    biome[height01 >= snow_level] = 5
    mask_rock = (height01 >= rock_level) & (height01 < snow_level); biome[mask_rock] = 4
    rest = ~((height01 < ocean_level) | mask_beach | (height01 >= rock_level))
    moist = moisture[rest]; tmp = np.zeros_like(moist, dtype=np.uint8)
    tmp[moist < 0.4] = 2; tmp[moist >= 0.4] = 3
    biome[rest] = tmp
    return biome


def biome_palette():
    import numpy as np
    return np.array([[10,40,120],[240,220,170],[95,180,60],[20,110,30],[130,130,130],[240,240,240]], dtype=np.uint8)


def test():
    pass