# Файл: game_engine_restructured/algorithms/climate/climate_helpers.py
from __future__ import annotations
import numpy as np
from numba import njit, prange

# =======================================================================
# ХЕЛПЕРЫ, СПЕЦИФИЧНЫЕ ДЛЯ КЛИМАТА И ГИДРОЛОГИИ
# =======================================================================

def _derive_seed(base: int, tag: str) -> int:
    h = 2166136261
    for b in tag.encode('utf-8'):
        h ^= b
        h = (h * 16777619) & 0xFFFFFFFF
    return (base ^ h) & 0xFFFFFFFF

@njit(cache=True, fastmath=True, parallel=True)
def _vectorized_smoothstep(edge0: float, edge1: float, x_array: np.ndarray) -> np.ndarray:
    out_flat = np.empty_like(x_array.ravel())
    in_flat = x_array.ravel()
    inv_span = 1.0 / (edge1 - edge0)
    for i in prange(in_flat.size):
        t = (in_flat[i] - edge0) * inv_span
        if t < 0.0: t = 0.0
        elif t > 1.0: t = 1.0
        out_flat[i] = t * t * (3.0 - 2.0 * t)
    return out_flat.reshape(x_array.shape)

# Функции _fbm_grid, _fbm_amplitude и все их Numba-зависимости УДАЛЕНЫ отсюда