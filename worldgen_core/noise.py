# --- заменить / добавить в noise.py ---

def fbm2(x, y, gen, octaves=6, lacunarity=2.0, gain=0.5, freq=1.0):
    amp = 1.0; val = 0.0; total = 0.0
    for _ in range(octaves):
        val += amp * gen.noise2(x * freq, y * freq)   # [-1..1]
        total += amp
        freq *= lacunarity
        amp  *= gain
    val = val / max(total, 1e-9)
    return 0.5 * (val + 1.0)                           # -> [0..1]

def ridge_fbm(x, y, gen, octaves=6, lacunarity=2.0, gain=0.5, freq=1.0, sharp=1.5):
    # "1 - |2n-1|" => гребни [0..1], sharp>1 делает пики резче
    n = fbm2(x, y, gen, octaves, lacunarity, gain, freq)
    r = 1.0 - abs(2.0 * n - 1.0)
    return r ** sharp

def height_block(seed, gx0, gy0, w, h,
                 plains_scale, plains_octaves,
                 mountains_scale, mountains_octaves,
                 mask_scale,
                 mountain_strength,
                 height_distribution_power,
                 lac, gain):
    from opensimplex import OpenSimplex
    import numpy as np
    gp = OpenSimplex(seed)
    gm = OpenSimplex(seed ^ 0x12345678)
    gk = OpenSimplex(seed ^ 0x87654321)

    inv_p = 1.0 / max(plains_scale,    1e-6)
    inv_m = 1.0 / max(mountains_scale, 1e-6)
    inv_k = 1.0 / max(mask_scale,      1e-6)

    def sstep(a,b,x):
        t = np.clip((x-a)/max(b-a,1e-6), 0.0, 1.0)
        return t*t*(3-2*t)

    out = np.empty((h, w), dtype=np.float32)
    for j in range(h):
        yy = gy0 + j
        row = out[j]
        for i in range(w):
            xx = gx0 + i
            plains = fbm2(xx*inv_p, yy*inv_p, gp, plains_octaves, lac, gain)
            ridge  = ridge_fbm(xx*inv_m, yy*inv_m, gm, mountains_octaves, lac, gain, sharp=1.5)
            mask   = fbm2(xx*inv_k, yy*inv_k, gk, 3, lac, gain)
            mask   = sstep(0.55, 0.75, mask)  # где можно ставить горы
            row[i] = np.clip(plains + mountain_strength * mask * ridge, 0.0, 1.0)

    if height_distribution_power != 1.0:
        out = np.power(out, height_distribution_power)
    return out
