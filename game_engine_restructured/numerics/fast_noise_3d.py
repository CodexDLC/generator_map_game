# game_engine_restructured/numerics/fast_noise_3d.py
from __future__ import annotations
import numpy as np
from numba import njit, prange
from .fast_noise_helpers import _hash3, _rand01_from_hash, _fade, _lerp, fbm_amplitude, F32


@njit(inline='always', cache=True)
def _grad3(hash_val: int, x: F32, y: F32, z: F32) -> F32:
    h = hash_val & 15
    u = y if h < 8 else z
    v = z if h < 4 else (x if (h == 12 or h == 14) else y)
    res = F32(0.0)
    if (h & 1) == 0:
        res += u
    else:
        res -= u
    if (h & 2) == 0:
        res += v
    else:
        res -= v
    return res


@njit(inline='always', cache=True)
def simplex_noise_3d_single(x: F32, y: F32, z: F32, seed: int) -> F32:
    F3 = F32(1.0 / 3.0)
    s = (x + y + z) * F3
    i, j, k = int(np.floor(x + s)), int(np.floor(y + s)), int(np.floor(z + s))

    G3 = F32(1.0 / 6.0)
    t = (i + j + k) * G3
    X0, Y0, Z0 = i - t, j - t, k - t
    x0, y0, z0 = x - X0, y - Y0, z - Z0

    if x0 >= y0:
        if y0 >= z0:
            i1, j1, k1 = 1, 0, 0; i2, j2, k2 = 1, 1, 0
        elif x0 >= z0:
            i1, j1, k1 = 1, 0, 0; i2, j2, k2 = 1, 0, 1
        else:
            i1, j1, k1 = 0, 0, 1; i2, j2, k2 = 1, 0, 1
    else:
        if y0 < z0:
            i1, j1, k1 = 0, 0, 1; i2, j2, k2 = 0, 1, 1
        elif x0 < z0:
            i1, j1, k1 = 0, 1, 0; i2, j2, k2 = 0, 1, 1
        else:
            i1, j1, k1 = 0, 1, 0; i2, j2, k2 = 1, 1, 0

    x1, y1, z1 = x0 - i1 + G3, y0 - j1 + G3, z0 - k1 + G3
    x2, y2, z2 = x0 - i2 + F32(2.0) * G3, y0 - j2 + F32(2.0) * G3, z0 - k2 + F32(2.0) * G3
    x3, y3, z3 = x0 - 1.0 + F32(3.0) * G3, y0 - 1.0 + F32(3.0) * G3, z0 - 1.0 + F32(3.0) * G3

    n = F32(0.0)
    t0 = F32(0.6) - x0 * x0 - y0 * y0 - z0 * z0
    if t0 > 0.0:
        t0 *= t0
        n += t0 * t0 * _grad3(_hash3(i, j, k, seed), x0, y0, z0)

    t1 = F32(0.6) - x1 * x1 - y1 * y1 - z1 * z1
    if t1 > 0.0:
        t1 *= t1
        n += t1 * t1 * _grad3(_hash3(i + i1, j + j1, k + k1, seed), x1, y1, z1)

    t2 = F32(0.6) - x2 * x2 - y2 * y2 - z2 * z2
    if t2 > 0.0:
        t2 *= t2
        n += t2 * t2 * _grad3(_hash3(i + i2, j + j2, k + k2, seed), x2, y2, z2)

    t3 = F32(0.6) - x3 * x3 - y3 * y3 - z3 * z3
    if t3 > 0.0:
        t3 *= t3
        n += t3 * t3 * _grad3(_hash3(i + 1, j + 1, k + 1, seed), x3, y3, z3)

    return F32(32.0) * n


# --- НАЧАЛО НОВОГО КОДА ---
@njit(cache=True, fastmath=True, parallel=True)
def simplex_noise_3d(
        coords_x: np.ndarray,
        coords_y: np.ndarray,
        coords_z: np.ndarray,
        seed: int
) -> np.ndarray:
    """
    Генерирует сетку 3D Simplex-шума. Векторизованная версия.
    """
    H, W = coords_x.shape
    output = np.empty((H, W), dtype=F32)
    for j in prange(H):
        for i in range(W):
            output[j, i] = simplex_noise_3d_single(
                coords_x[j, i],
                coords_y[j, i],
                coords_z[j, i],
                seed
            )
    return output
# --- КОНЕЦ НОВОГО КОДА ---


@njit(cache=True, fastmath=True, parallel=True)
def fbm_grid_3d(
        seed: int,
        coords_x: np.ndarray,
        coords_y: np.ndarray,
        coords_z: np.ndarray,
        freq0: F32,
        octaves: int,
        gain: F32 = F32(0.5),
        ridge: bool = False
) -> np.ndarray:
    H, W = coords_x.shape
    output = np.empty((H, W), dtype=F32)
    lacunarity = F32(2.0)

    for j in prange(H):
        for i in range(W):
            amp, freq, total = F32(1.0), freq0, F32(0.0)
            for o in range(octaves):
                sample = simplex_noise_3d_single(
                    coords_x[j, i] * freq,
                    coords_y[j, i] * freq,
                    coords_z[j, i] * freq,
                    seed + o
                )
                if ridge:
                    sample = (F32(1.0) - abs(sample)) * F32(2.0) - F32(1.0)

                total += amp * sample
                freq *= lacunarity
                amp *= gain
            output[j, i] = total

    max_amp = fbm_amplitude(gain, octaves)
    if max_amp > 1e-6:
        output /= max_amp

    return output