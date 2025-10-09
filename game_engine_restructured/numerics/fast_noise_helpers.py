# game_engine_restructured/numerics/fast_noise_helpers.py
from __future__ import annotations
import numpy as np
from numba import njit

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
    a = _u32(a + ix); b = _u32(b + iz); c = _u32(c + seed)
    a = _u32(a - b - c) ^ (c >> 13); b = _u32(b - c - a) ^ (a << 8); c = _u32(c - a - b) ^ (b >> 13)
    a = _u32(a - b - c) ^ (c >> 12); b = _u32(b - c - a) ^ (a << 16); c = _u32(c - a - b) ^ (b >> 5)
    a = _u32(a - b - c) ^ (c >> 3); b = _u32(b - c - a) ^ (a << 10); c = _u32(c - a - b) ^ (b >> 15)
    return _u32(c)

@njit(inline='always', cache=True)
def _hash3(ix: int, iy: int, iz: int, seed: int) -> int:
    a, b, c = 0x9e3779b3, 0x9e3779b3, _u32(seed)
    a = _u32(a + ix); b = _u32(b + iy); c = _u32(c + iz)
    a = _u32(a - b - c) ^ (c >> 13); b = _u32(b - c - a) ^ (a << 8); c = _u32(c - a - b) ^ (b >> 13)
    a = _u32(a - b - c) ^ (c >> 12); b = _u32(b - c - a) ^ (a << 16); c = _u32(c - a - b) ^ (b >> 5)
    a = _u32(a - b - c) ^ (c >> 3); b = _u32(b - c - a) ^ (a << 10); c = _u32(c - a - b) ^ (b >> 15)
    return c

@njit(inline='always', cache=True)
def _rand01_from_hash(h: int) -> F32:
    return F32(h) / F32(4294967296.0)

@njit(inline='always', cache=True)
def _fade(t: F32) -> F32:
    return t * t * t * (t * (t * F32(6.0) - F32(15.0)) + F32(10.0))

@njit(inline='always', cache=True)
def _lerp(a: F32, b: F32, t: F32) -> F32:
    return a + (b - a) * t