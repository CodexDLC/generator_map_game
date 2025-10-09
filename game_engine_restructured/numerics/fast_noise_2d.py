# game_engine_restructured/numerics/fast_noise_2d.py
from __future__ import annotations
import numpy as np
from numba import njit, prange
from .fast_noise_helpers import _hash2, _rand01_from_hash, _fade, _lerp, fbm_amplitude, F32

@njit(inline='always', cache=True)
def value_noise_2d(x: F32, z: F32, seed: int) -> F32:
    xi, zi = int(np.floor(x)), int(np.floor(z))
    xf, zf = x - xi, z - zi
    u, v = _fade(xf), _fade(zf)
    n00 = _rand01_from_hash(_hash2(xi, zi, seed)); n10 = _rand01_from_hash(_hash2(xi + 1, zi, seed))
    n01 = _rand01_from_hash(_hash2(xi, zi + 1, seed)); n11 = _rand01_from_hash(_hash2(xi + 1, zi + 1, seed))
    nx0 = _lerp(n00, n10, u); nx1 = _lerp(n01, n11, u)
    return _lerp(nx0, nx1, v)

@njit(cache=True, fastmath=True, parallel=True)
def fbm_grid_bipolar(
        seed: int,
        coords_x: np.ndarray,
        coords_z: np.ndarray,
        freq0: F32,
        octaves: int,
        ridge: bool,
        lacunarity: F32 = F32(2.0),
        gain: F32 = F32(0.5)
) -> np.ndarray:
    H, W = coords_x.shape
    output = np.empty_like(coords_x, dtype=F32)
    for j in prange(H):
        for i in range(W):
            cx, cz = coords_x[j, i], coords_z[j, i]
            amp, freq, total = F32(1.0), freq0, F32(0.0)
            for o in range(octaves):
                noise_val = value_noise_2d(cx * freq, cz * freq, seed + o)
                sample = noise_val * F32(2.0) - F32(1.0)
                if ridge:
                    sample = (F32(1.0) - abs(sample)) * F32(2.0) - F32(1.0)
                total += amp * sample
                freq *= lacunarity
                amp *= gain
            output[j, i] = total
    return output