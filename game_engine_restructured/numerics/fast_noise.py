# ==============================================================================
# Файл: game_engine_restructured/numerics/fast_noise.py (ВЕРСИЯ 2.5 - Typing Fix)
# ИСПРАВЛЕНИЕ: Убрана ошибочная условная логика в fbm_grid_3d,
#              которая приводила к ошибке типизации в Numba.
# ==============================================================================
from __future__ import annotations
import numpy as np
import math
from numba import njit, prange

F32 = np.float32


@njit(cache=True)
def fbm_amplitude(gain: float, octaves: int) -> float:
    if gain == 1.0:
        return float(octaves)
    return (1.0 - gain ** octaves) / (1.0 - gain)


@njit(inline='always', cache=True)
def _u32(x: int) -> int: return x & 0xFFFFFFFF


@njit(inline='always', cache=True)
def _hash2(ix: int, iz: int, seed: int) -> int:
    a, b, c = 0x9e3779b3, 0x9e3779b3, 0x9e3779b3
    a = _u32(a + ix);
    b = _u32(b + iz);
    c = _u32(c + seed)
    a = _u32(a - b - c) ^ (c >> 13);
    b = _u32(b - c - a) ^ (a << 8);
    c = _u32(c - a - b) ^ (b >> 13)
    a = _u32(a - b - c) ^ (c >> 12);
    b = _u32(b - c - a) ^ (a << 16);
    c = _u32(c - a - b) ^ (b >> 5)
    a = _u32(a - b - c) ^ (c >> 3);
    b = _u32(b - c - a) ^ (a << 10);
    c = _u32(c - a - b) ^ (b >> 15)
    return _u32(c)


@njit(inline='always', cache=True)
def _hash3(ix: int, iy: int, iz: int, seed: int) -> int:
    a, b, c = 0x9e3779b3, 0x9e3779b3, _u32(seed)
    a = _u32(a + ix);
    b = _u32(b + iy);
    c = _u32(c + iz)
    a = _u32(a - b - c) ^ (c >> 13);
    b = _u32(b - c - a) ^ (a << 8);
    c = _u32(c - a - b) ^ (b >> 13)
    a = _u32(a - b - c) ^ (c >> 12);
    b = _u32(b - c - a) ^ (a << 16);
    c = _u32(c - a - b) ^ (b >> 5)
    a = _u32(a - b - c) ^ (c >> 3);
    b = _u32(b - c - a) ^ (a << 10);
    c = _u32(c - a - b) ^ (b >> 15)
    return c


@njit(inline='always', cache=True)
def _rand01_from_hash(h: int) -> F32:
    return F32(h) / F32(4294967296.0)


@njit(inline='always', cache=True)
def _rand01(ix: int, iz: int, seed: int) -> F32:
    return _rand01_from_hash(_hash2(ix, iz, seed))


@njit(inline='always', cache=True)
def _fade(t: F32) -> F32:
    return t * t * t * (t * (t * F32(6.0) - F32(15.0)) + F32(10.0))


@njit(inline='always', cache=True)
def _lerp(a: F32, b: F32, t: F32) -> F32:
    return a + (b - a) * t


@njit(inline='always', cache=True)
def value_noise_2d(x: F32, z: F32, seed: int) -> F32:
    xi = int(np.floor(x));
    zi = int(np.floor(z))
    xf = x - xi;
    zf = z - zi
    u = _fade(xf);
    v = _fade(zf)
    n00 = _rand01(xi, zi, seed);
    n10 = _rand01(xi + 1, zi, seed)
    n01 = _rand01(xi, zi + 1, seed);
    n11 = _rand01(xi + 1, zi + 1, seed)
    nx0 = _lerp(n00, n10, u);
    nx1 = _lerp(n01, n11, u)
    return _lerp(nx0, nx1, v)


@njit(inline='always', cache=True)
def value_noise_3d(x: F32, y: F32, z: F32, seed: int) -> F32:
    xi, yi, zi = int(np.floor(x)), int(np.floor(y)), int(np.floor(z))
    xf, yf, zf = x - xi, y - yi, z - zi
    u, v, w = _fade(xf), _fade(yf), _fade(zf)
    n000 = _rand01_from_hash(_hash3(xi, yi, zi, seed))
    n100 = _rand01_from_hash(_hash3(xi + 1, yi, zi, seed))
    n010 = _rand01_from_hash(_hash3(xi, yi + 1, zi, seed))
    n110 = _rand01_from_hash(_hash3(xi + 1, yi + 1, zi, seed))
    n001 = _rand01_from_hash(_hash3(xi, yi, zi + 1, seed))
    n101 = _rand01_from_hash(_hash3(xi + 1, yi, zi + 1, seed))
    n011 = _rand01_from_hash(_hash3(xi, yi + 1, zi + 1, seed))
    n111 = _rand01_from_hash(_hash3(xi + 1, yi + 1, zi + 1, seed))
    nx00 = _lerp(n000, n100, u);
    nx10 = _lerp(n010, n110, u)
    nx01 = _lerp(n001, n101, u);
    nx11 = _lerp(n011, n111, u)
    nxy0 = _lerp(nx00, nx10, v);
    nxy1 = _lerp(nx01, nx11, v)
    return _lerp(nxy0, nxy1, w)


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
            cx = coords_x[j, i];
            cz = coords_z[j, i]
            amp = F32(1.0);
            freq = freq0;
            total = F32(0.0)
            for o in range(octaves):
                noise_val = value_noise_2d(cx * freq, cz * freq, seed + o)
                sample = noise_val * F32(2.0) - F32(1.0)
                if ridge:
                    sample = (F32(1.0) - abs(sample)) * F32(2.0) - F32(1.0)
                total += amp * sample
                freq *= lacunarity;
                amp *= gain
            output[j, i] = total
    return output


@njit(cache=True, fastmath=True)
def fbm_grid_3d(
        seed: int,
        coords_x: np.ndarray,
        coords_y: np.ndarray,
        coords_z: np.ndarray,
        freq0: F32,
        octaves: int,
        ridge: bool,
        lacunarity: F32 = F32(2.0),
        gain: F32 = F32(0.5)
) -> np.ndarray:
    H, W = coords_x.shape
    output = np.empty_like(coords_x, dtype=F32)

    for j in range(H):
        for i in range(W):
            # --- FIX: Always use 2D indexing as input arrays are guaranteed to be 2D. ---
            cx = coords_x[j, i]
            cy = coords_y[j, i]
            cz = coords_z[j, i]
            # --- END FIX ---

            amp, freq, total = F32(1.0), freq0, F32(0.0)
            for o in range(octaves):
                sample = value_noise_3d(cx * freq, cy * freq, cz * freq, seed + o) * F32(2.0) - F32(1.0)
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

