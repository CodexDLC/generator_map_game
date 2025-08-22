import numpy as np
from opensimplex import OpenSimplex

def fbm2(x, y, gen: OpenSimplex, octaves=6, lacunarity=2.0, gain=0.5, freq=1.0):
    amp = 1.0; val = 0.0
    for _ in range(octaves):
        val += amp * gen.noise2(x * freq, y * freq)
        freq *= lacunarity; amp *= gain
    return 0.5 * (val / (1.0 if octaves == 1 else (1 - gain)) + 1.0)

def height_block(seed: int, gx0: int, gy0: int, w: int, h: int,
                 scale: float, octaves: int, lac: float, gain: float):
    gen = OpenSimplex(seed)
    out = np.zeros((h, w), dtype=np.float32)
    inv = 1.0 / max(scale, 1e-6)
    for j in range(h):
        yy = (gy0 + j) * inv
        row = out[j]
        for i in range(w):
            xx = (gx0 + i) * inv
            row[i] = fbm2(xx, yy, gen, octaves=octaves, lacunarity=lac, gain=gain, freq=1.0)
    return out
