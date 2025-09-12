# Файл: game_engine_restructured/algorithms/climate/climate_helpers.py
from __future__ import annotations
import numpy as np
import math
from scipy.ndimage import distance_transform_edt, gaussian_filter
from numba import njit, prange

# =======================================================================
# БЛОК 1: ОБЫЧНЫЕ PYTHON ХЕЛПЕРЫ
# =======================================================================

def _stats(name: str, arr: np.ndarray):
    """Выводит отладочную статистику для массива."""
    print(f"[STAT] {name:>12} min={arr.min():7.3f} max={arr.max():7.3f} mean={arr.mean():7.3f}")

def _derive_seed(base: int, tag: str) -> int:
    """Детерминированно порождает новый seed из базового и строки-тега."""
    h = 2166136261
    for b in tag.encode('utf-8'):
        h ^= b
        h = (h * 16777619) & 0xFFFFFFFF
    return (base ^ h) & 0xFFFFFFFF

def _fbm_amplitude(gain: float, octaves: int) -> float:
    """Вычисляет теоретическую максимальную амплитуду fBm для глобальной нормализации."""
    if gain == 1.0:
        return float(octaves)
    return (1.0 - gain**octaves) / (1.0 - gain)

def _pad_reflect(arr: np.ndarray, pad: int) -> np.ndarray:
    """Добавляет 'ореол' к массиву, отражая его края."""
    return np.pad(arr, pad_width=pad, mode='reflect')

def _edt_with_halo(mask: np.ndarray, pad: int, mpp: float) -> np.ndarray:
    """Выполняет Distance Transform с 'ореолом', чтобы избежать краевых артефактов."""
    pad_mask = _pad_reflect(mask, pad)
    d = distance_transform_edt(~pad_mask)
    return d[pad:-pad, pad:-pad] * mpp

# =======================================================================
# БЛОК 2: NUMBA JIT ХЕЛПЕРЫ (ДЛЯ ВЫСОКОЙ ПРОИЗВОДИТЕЛЬНОСТИ)
# =======================================================================

@njit(inline='always', cache=True)
def _smoothstep(edge0: float, edge1: float, x: float) -> float:
    """Гладкая пороговая функция."""
    t = (x - edge0) / (edge1 - edge0)
    t = max(0.0, min(1.0, t))
    return t * t * (3.0 - 2.0 * t)

@njit(cache=True, fastmath=True, parallel=True)
def _vectorized_smoothstep(edge0: float, edge1: float, x_array: np.ndarray) -> np.ndarray:
    """Применяет smoothstep ко всему массиву, работая с плоским представлением."""
    out_flat = np.empty_like(x_array.ravel())
    in_flat = x_array.ravel()
    inv_span = 1.0 / (edge1 - edge0)
    for i in prange(in_flat.size):
        t = (in_flat[i] - edge0) * inv_span
        if t < 0.0:
            t = 0.0
        elif t > 1.0:
            t = 1.0
        out_flat[i] = t * t * (3.0 - 2.0 * t)
    return out_flat.reshape(x_array.shape)

@njit(inline='always', cache=True)
def _u32(x: int) -> int: return x & 0xFFFFFFFF

@njit(inline='always', cache=True)
def _hash2(ix: int, iz: int, seed: int) -> int:
    a = _u32(0x9e3779b1 + 2); b = a; c = a
    a = _u32(a + ix);  b = _u32(b + iz);  c = _u32(c + seed)
    a = _u32(a - b); a = _u32(a - c); a = _u32(a ^ (c >> 13))
    b = _u32(b - c); b = _u32(b - a); b = _u32(b ^ (a << 8))
    c = _u32(c - a); c = _u32(c - b); c = _u32(c ^ (b >> 13))
    a = _u32(a - b); a = _u32(a - c); a = _u32(a ^ (c >> 12))
    b = _u32(b - c); b = _u32(b - a); b = _u32(b ^ (a << 16))
    c = _u32(c - a); c = _u32(c - b); c = _u32(c ^ (b >> 5))
    a = _u32(a - b); a = _u32(a - c); a = _u32(a ^ (c >> 3))
    b = _u32(b - c); b = _u32(b - a); b = _u32(b ^ (a << 10))
    c = _u32(c - a); c = _u32(c - b); c = _u32(c ^ (b >> 15))
    return _u32(c)

@njit(inline='always', cache=True)
def _rand01(ix: int, iz: int, seed: int) -> float: return _hash2(ix, iz, seed) / 4294967296.0

@njit(inline='always', cache=True)
def _fade(t: float) -> float: return t*t*t*(t*(t*6.0-15.0)+10.0)

@njit(inline='always', cache=True)
def _lerp(a: float, b: float, t: float) -> float: return a + (b-a)*t

@njit(inline='always', cache=True)
def _value_noise_2d(x: float, z: float, seed: int) -> float:
    xi=int(np.floor(x)); xf=x-xi; zi=int(np.floor(z)); zf=z-zi
    u=_fade(xf); v=_fade(zf)
    n00=_rand01(xi,zi,seed); n10=_rand01(xi+1,zi,seed); n01=_rand01(xi,zi+1,seed); n11=_rand01(xi+1,zi+1,seed)
    nx0=_lerp(n00,n10,u); nx1=_lerp(n01,n11,u)
    return _lerp(nx0,nx1,v)

@njit(cache=True)
def _fbm_grid(seed: int, x0_px: int, z0_px: int, size: int, mpp: float, freq0: float,
              octaves: int, lacunarity: float, gain: float, rot_deg: float) -> np.ndarray:
    g = np.zeros((size, size), dtype=np.float32)
    cr = math.cos(math.radians(rot_deg)); sr = math.sin(math.radians(rot_deg))
    for o in range(octaves):
        amp = gain ** o
        freq = freq0 * (lacunarity ** o)
        for j in range(size):
            wz_m = (z0_px + j) * mpp
            for i in range(size):
                wx_m = (x0_px + i) * mpp
                rx = cr * wx_m - sr * wz_m; rz = sr * wx_m + cr * wz_m
                noise_val = _value_noise_2d(rx * freq, rz * freq, seed + o)
                g[j, i] += amp * (noise_val * 2.0 - 1.0)
    return g