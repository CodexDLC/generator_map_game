# ==============================================================================
# Файл: game_engine_restructured/numerics/fast_noise.py (ВЕРСИЯ 2.1 - F32)
# ИСПРАВЛЕНИЕ: Все функции переведены на явное использование float32
# для устранения артефактов квантования (блочности).
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
    a = _u32(a + ix)
    b = _u32(b + iz)
    c = _u32(c + seed)
    a = _u32(a - b - c) ^ (c >> 13)
    b = _u32(b - c - a) ^ (a << 8)
    c = _u32(c - a - b) ^ (b >> 13)
    a = _u32(a - b - c) ^ (c >> 12)
    b = _u32(b - c - a) ^ (a << 16)
    c = _u32(c - a - b) ^ (b >> 5)
    a = _u32(a - b - c) ^ (c >> 3)
    b = _u32(b - c - a) ^ (a << 10)
    c = _u32(c - a - b) ^ (b >> 15)
    return _u32(c)

@njit(inline='always', cache=True)
def _rand01(ix: int, iz: int, seed: int) -> F32:
    return F32(_hash2(ix, iz, seed)) / F32(4294967296.0)

@njit(inline='always', cache=True)
def _fade(t: F32) -> F32:
    return t * t * t * (t * (t * F32(6.0) - F32(15.0)) + F32(10.0))

@njit(inline='always', cache=True)
def _lerp(a: F32, b: F32, t: F32) -> F32:
    return a + (b - a) * t

@njit(inline='always', cache=True)
def value_noise_2d(x: F32, z: F32, seed: int) -> F32:
    xi = int(np.floor(x))
    zi = int(np.floor(z))
    xf = x - xi
    zf = z - zi
    u = _fade(xf)
    v = _fade(zf)
    n00 = _rand01(xi, zi, seed)
    n10 = _rand01(xi + 1, zi, seed)
    n01 = _rand01(xi, zi + 1, seed)
    n11 = _rand01(xi + 1, zi + 1, seed)
    nx0 = _lerp(n00, n10, u)
    nx1 = _lerp(n01, n11, u)
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
            cx = coords_x[j, i]
            cz = coords_z[j, i]

            amp = F32(1.0)
            freq = freq0
            total = F32(0.0)
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

@njit(cache=True, fastmath=True, parallel=True)
def fbm_grid(
        seed: int, x0_px: int, z0_px: int, size: int, mpp: F32, freq0: F32,
        octaves: int, lacunarity: F32 = F32(2.0), gain: F32 = F32(0.5), rot_deg: F32 = F32(0.0),
        ridge: bool = False
) -> np.ndarray:
    g = np.zeros((size, size), dtype=F32)
    cr, sr = math.cos(math.radians(rot_deg)), math.sin(math.radians(rot_deg))

    for j in prange(size):
        wz_m = (z0_px + j) * mpp
        for i in range(size):
            wx_m = (x0_px + i) * mpp
            rx = cr * wx_m - sr * wz_m
            rz = sr * wx_m + cr * wz_m

            amp = F32(1.0)
            freq = freq0
            total = F32(0.0)

            for o in range(octaves):
                noise_val = value_noise_2d(rx * freq, rz * freq, seed + o)
                sample = noise_val * F32(2.0) - F32(1.0)

                if ridge:
                    sample = (F32(1.0) - abs(sample)) * F32(2.0) - F32(1.0)

                total += amp * sample
                freq *= lacunarity
                amp *= gain

            g[j, i] = total

    return g

@njit(cache=True, fastmath=True, parallel=True)
def fbm_grid_warped(
        seed: int,
        coords_x: np.ndarray,
        coords_z: np.ndarray,
        freq0: F32,
        octaves: int,
        ridge: bool,
        warp_seed: int = 0,
        warp_amp: F32 = F32(0.0),
        warp_freq: F32 = F32(0.0),
        warp_octaves: int = 2,
        lacunarity: F32 = F32(2.0),
        gain: F32 = F32(0.5)
) -> np.ndarray:
    H, W = coords_x.shape
    output = np.empty_like(coords_x, dtype=F32)

    for j in prange(H):
        for i in range(W):
            cx = coords_x[j, i]
            cz = coords_z[j, i]

            if warp_amp > 0.0:
                offset_x = F32(0.0)
                warp_amp_iter_x = F32(1.0)
                warp_freq_iter_x = warp_freq
                for _ in range(warp_octaves):
                    noise_val = value_noise_2d(cx * warp_freq_iter_x, cz * warp_freq_iter_x, warp_seed)
                    offset_x += (noise_val * F32(2.0) - F32(1.0)) * warp_amp_iter_x
                    warp_freq_iter_x *= lacunarity
                    warp_amp_iter_x *= gain

                offset_z = F32(0.0)
                warp_amp_iter_z = F32(1.0)
                warp_freq_iter_z = warp_freq
                for _ in range(warp_octaves):
                    noise_val = value_noise_2d(cx * warp_freq_iter_z, cz * warp_freq_iter_z, warp_seed + 1)
                    offset_z += (noise_val * F32(2.0) - F32(1.0)) * warp_amp_iter_z
                    warp_freq_iter_z *= lacunarity
                    warp_amp_iter_z *= gain

                cx += offset_x * warp_amp
                cz += offset_z * warp_amp

            amp = F32(1.0)
            freq = freq0
            total = F32(0.0)
            for o in range(octaves):
                noise_val = value_noise_2d(cx * freq, cz * freq, seed + o)
                sample = noise_val * F32(2.0) - F32(1.0)

                if ridge:
                    sample = F32(1.0) - abs(sample)

                total += amp * sample
                freq *= lacunarity
                amp *= gain

            output[j, i] = total
    return output

@njit(cache=True, fastmath=True)
def xorshift32(state: np.uint32) -> np.uint32:
    s = state
    s ^= (s << np.uint32(13))
    s ^= (s >> np.uint32(17))
    s ^= (s << np.uint32(5))
    return s & np.uint32(0x7FFFFFFF)

@njit(cache=True, fastmath=True, parallel=True)
def voronoi_grid(seed: int, coords_x: np.ndarray, coords_z: np.ndarray, freq0: F32) -> np.ndarray:
    H, W = coords_x.shape
    if freq0 <= 0.0:
        out = np.empty((H, W), dtype=F32)
        for i in prange(H):
            for j in range(W):
                out[i, j] = F32(1.0)
        return out

    scaled_x = coords_x * freq0
    scaled_z = coords_z * freq0
    R = 2
    sx_min = math.floor(np.min(scaled_x))
    sx_max = math.ceil(np.max(scaled_x))
    sz_min = math.floor(np.min(scaled_z))
    sz_max = math.ceil(np.max(scaled_z))
    grid_min_x = int(sx_min) - R
    grid_max_x = int(sx_max) + 1 + R
    grid_min_z = int(sz_min) - R
    grid_max_z = int(sz_max) + 1 + R
    out = np.empty((H, W), dtype=F32)

    for i in prange(H):
        for j in range(W):
            x = scaled_x[i, j]
            z = scaled_z[i, j]
            cx = int(math.floor(x))
            cz = int(math.floor(z))
            d1 = np.inf
            d2 = np.inf
            for ox in range(-R, R + 1):
                cell_x = cx + ox
                if cell_x < grid_min_x or cell_x >= grid_max_x:
                    continue
                for oz in range(-R, R + 1):
                    cell_z = cz + oz
                    if cell_z < grid_min_z or cell_z >= grid_max_z:
                        continue
                    h = np.uint32(seed) ^ np.uint32(cell_x * 73856093) ^ np.uint32(cell_z * 83492791)
                    jx = F32(xorshift32(h)) / F32(2147483647.0)
                    jz = F32(xorshift32(h ^ np.uint32(0x9E3779B9))) / F32(2147483647.0)
                    px = F32(cell_x) + jx
                    pz = F32(cell_z) + jz
                    dx = x - px
                    dz = z - pz
                    d2cur = dx * dx + dz * dz
                    if d2cur < d1:
                        d2 = d1
                        d1 = d2cur
                    elif d2cur < d2:
                        d2 = d2cur
            diff = d2 - d1
            k = F32(4.0)
            val = F32(1.0) - math.exp(-k * diff)
            if val < 0.0:
                val = F32(0.0)
            elif val > 1.0:
                val = F32(1.0)
            out[i, j] = val

    return out

@njit(cache=True, fastmath=True, parallel=True)
def fbm_grid_warped_bipolar(
        seed: int,
        coords_x: np.ndarray,
        coords_z: np.ndarray,
        freq0: F32,
        octaves: int,
        ridge: bool,
        warp_seed: int = 0,
        warp_amp: F32 = F32(0.0),
        warp_freq: F32 = F32(0.0),
        warp_octaves: int = 2,
        lacunarity: F32 = F32(2.0),
        gain: F32 = F32(0.5)
) -> np.ndarray:
    H, W = coords_x.shape
    output = np.empty_like(coords_x, dtype=F32)

    for j in prange(H):
        for i in range(W):
            cx = coords_x[j, i]
            cz = coords_z[j, i]

            if warp_amp > 0.0:
                offset_x = F32(0.0)
                warp_amp_iter_x = F32(1.0)
                warp_freq_iter_x = warp_freq
                for _ in range(warp_octaves):
                    noise_val = value_noise_2d(cx * warp_freq_iter_x, cz * warp_freq_iter_x, warp_seed)
                    offset_x += (noise_val * F32(2.0) - F32(1.0)) * warp_amp_iter_x
                    warp_freq_iter_x *= lacunarity
                    warp_amp_iter_x *= gain

                offset_z = F32(0.0)
                warp_amp_iter_z = F32(1.0)
                warp_freq_iter_z = warp_freq
                for _ in range(warp_octaves):
                    noise_val = value_noise_2d(cx * warp_freq_iter_z, cz * warp_freq_iter_z, warp_seed + 1)
                    offset_z += (noise_val * F32(2.0) - F32(1.0)) * warp_amp_iter_z
                    warp_freq_iter_z *= lacunarity
                    warp_amp_iter_z *= gain

                cx += offset_x * warp_amp
                cz += offset_z * warp_amp

            amp = F32(1.0)
            freq = freq0
            total = F32(0.0)
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
