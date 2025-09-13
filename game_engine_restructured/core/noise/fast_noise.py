# ==============================================================================
# Файл: game_engine_restructured/core/noise/fast_noise.py
# Назначение: Высокопроизводительные функции для генерации шума с Numba.
# ==============================================================================
from __future__ import annotations
import numpy as np
import math
from numba import njit, prange


def fbm_amplitude(gain: float, octaves: int) -> float:
    """
    Вычисляет теоретическую максимальную амплитуду fBm для нормализации.
    Это нужно, чтобы результат шума всегда был в диапазоне [-1, 1].
    """
    if gain == 1.0:
        return float(octaves)
    return (1.0 - gain ** octaves) / (1.0 - gain)


# --- Вспомогательные Numba-функции (внутренняя "магия") ---

@njit(inline='always', cache=True)
def _u32(x: int) -> int: return x & 0xFFFFFFFF


@njit(inline='always', cache=True)
def _hash2(ix: int, iz: int, seed: int) -> int:
    a, b, c = 0x9e3779b3, 0x9e3779b3, 0x9e3779b3
    a = _u32(a + ix);
    b = _u32(b + iz);
    c = _u32(c + seed)
    a = _u32(a - b - c) ^ (c >> 13);
    b = _u32(b - c - a) ^ (a << 8)
    c = _u32(c - a - b) ^ (b >> 13);
    a = _u32(a - b - c) ^ (c >> 12)
    b = _u32(b - c - a) ^ (a << 16);
    c = _u32(c - a - b) ^ (b >> 5)
    a = _u32(a - b - c) ^ (c >> 3);
    b = _u32(b - c - a) ^ (a << 10)
    c = _u32(c - a - b) ^ (b >> 15)
    return _u32(c)


@njit(inline='always', cache=True)
def _rand01(ix: int, iz: int, seed: int) -> float:
    return _hash2(ix, iz, seed) / 4294967296.0


@njit(inline='always', cache=True)
def _fade(t: float) -> float:
    return t * t * t * (t * (t * 6.0 - 15.0) + 10.0)


@njit(inline='always', cache=True)
def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


@njit(inline='always', cache=True)
def value_noise_2d(x: float, z: float, seed: int) -> float:
    """
    Базовая функция Value Noise 2D. Возвращает значение в диапазоне [0, 1].
    """
    xi, zi = int(np.floor(x)), int(np.floor(z))
    xf, zf = x - xi, z - zi
    u, v = _fade(xf), _fade(zf)
    n00 = _rand01(xi, zi, seed);
    n10 = _rand01(xi + 1, zi, seed)
    n01 = _rand01(xi, zi + 1, seed);
    n11 = _rand01(xi + 1, zi + 1, seed)
    nx0 = _lerp(n00, n10, u);
    nx1 = _lerp(n01, n11, u)
    return _lerp(nx0, nx1, v)


# --- Основная публичная функция ---

@njit(cache=True, fastmath=True, parallel=True)
def fbm_grid(
        seed: int, x0_px: int, z0_px: int, size: int, mpp: float, freq0: float,
        octaves: int, lacunarity: float = 2.0, gain: float = 0.5, rot_deg: float = 0.0,
        ridge: bool = False  # <--- ДОБАВЛЕН НОВЫЙ ПАРАМЕТР
) -> np.ndarray:
    """
    Генерирует 2D-массив фрактального шума (fBm) с помощью Value Noise.
    Возвращает массив со значениями в диапазоне [-amp, amp].
    """
    g = np.zeros((size, size), dtype=np.float32)
    cr, sr = math.cos(math.radians(rot_deg)), math.sin(math.radians(rot_deg))

    for j in prange(size):
        wz_m = (z0_px + j) * mpp
        for i in range(size):
            wx_m = (x0_px + i) * mpp
            rx = cr * wx_m - sr * wz_m
            rz = sr * wx_m + cr * wz_m

            amp = 1.0
            freq = freq0
            total = 0.0

            for o in range(octaves):
                noise_val = value_noise_2d(rx * freq, rz * freq, seed + o)
                sample = noise_val * 2.0 - 1.0  # Смещаем [0, 1] -> [-1, 1]

                # --- ДОБАВЛЕНА ЛОГИКА RIDGE ---
                if ridge:
                    sample = (1.0 - abs(sample)) * 2.0 - 1.0

                total += amp * sample
                freq *= lacunarity
                amp *= gain

            g[j, i] = total

    return g