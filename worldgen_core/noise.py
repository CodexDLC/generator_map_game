def fbm2(x, y, gen, octaves=6, lacunarity=2.0, gain=0.5, freq=1.0):
    amp = 1.0
    val = 0.0
    total = 0.0
    for _ in range(octaves):
        val += amp * gen.noise2(x * freq, y * freq)   # [-1..1]
        total += amp
        freq *= lacunarity
        amp *= gain
    if total > 0:
        val /= total                                  # нормализация по сумме амплитуд
    return 0.5 * (val + 1.0)                          # -> [0..1]

def height_block(seed, gx0, gy0, w, h,
                 plains_scale, plains_octaves,
                 mountains_scale, mountains_octaves,
                 mask_scale,
                 mountain_strength,
                 height_distribution_power,
                 lac, gain):
    from opensimplex import OpenSimplex
    import numpy as np
    gen_plains = OpenSimplex(seed)
    gen_mountains = OpenSimplex(seed ^ 0x12345678)
    gen_mask = OpenSimplex(seed ^ 0x87654321)

    out = np.zeros((h, w), dtype=np.float32)
    inv_plains = 1.0 / max(plains_scale, 1e-6)
    inv_mountains = 1.0 / max(mountains_scale, 1e-6)
    inv_mask = 1.0 / max(mask_scale, 1e-6)

    def smoothstep(a, b, x):
        t = np.clip((x - a) / max(b - a, 1e-6), 0.0, 1.0)
        return t * t * (3 - 2 * t)

    for j in range(h):
        row = out[j]
        yy = gy0 + j
        for i in range(w):
            xx = gx0 + i

            # Равнины — мягкий fBm
            plains = fbm2(xx * inv_plains, yy * inv_plains, gen_plains,
                          octaves=plains_octaves, lacunarity=lac, gain=gain)

            # Горы — ridged fBm: "1 - |2n-1|" даёт гребни в [0..1]
            n = fbm2(xx * inv_mountains, yy * inv_mountains, gen_mountains,
                     octaves=mountains_octaves, lacunarity=lac, gain=gain)
            ridge = 1.0 - abs(2.0 * n - 1.0)
            ridge = ridge ** 1.5      # чуть резче пики

            # Маска размещения гор — более узкая зона
            m = fbm2(xx * inv_mask, yy * inv_mask, gen_mask,
                     octaves=3, lacunarity=lac, gain=gain)
            m = smoothstep(0.55, 0.75, m)  # пороговая S-кривая вместо *1.5-0.25

            row[i] = np.clip(plains + mountain_strength * m * ridge, 0.0, 1.0)

    if height_distribution_power != 1.0:
        out = np.power(out, height_distribution_power)
    return out