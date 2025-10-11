# generator_logic/terrain/core/warp.py
from __future__ import annotations
import numpy as np
from numba import njit

# --- ИЗМЕНЕНИЕ: Исправлен импорт на fast_noise_2d ---
from game_engine_restructured.numerics.fast_noise_2d import value_noise_2d

F32 = np.float32

@njit(cache=True, fastmath=True)
def fbm_for_warp(x_m, z_m, octaves, gain, seed):
    """FBM-шум, используемый для генерации векторов смещения в доменном варпе."""
    amp = F32(1.0)
    freq = F32(1.0)
    total = F32(0.0)
    norm = F32(0.0)
    for i in range(octaves):
        n = value_noise_2d(x_m * freq, z_m * freq, seed + i) * F32(2.0) - F32(1.0)
        total += amp * n
        norm  += amp
        amp   *= F32(gain)
        freq  *= F32(2.0)
    return F32(0.0) if norm < F32(1e-6) else total / norm

@njit(cache=True, fastmath=True)
def apply_domain_warp(wx, wz,
                      base_freq_1pm,   # 1/м
                      amp0_m,          # м
                      complexity,      # октавы FBM внутри варпа
                      roughness,       # gain FBM
                      iterations,      # число итераций
                      attenuation,     # 0..1
                      anisotropy,      # отношение X/Z
                      seed):
    """Итеративный доменный варп, применяемый в координатах реального мира (метрах)."""
    amp = F32(amp0_m)
    freq = F32(base_freq_1pm)
    an = F32(anisotropy)
    inv_an = F32(1.0) / (an if an > F32(1e-6) else F32(1.0))
    for it in range(iterations):
        dx = fbm_for_warp(wx * freq, wz * freq, complexity, F32(roughness), seed + it * 101)
        dz = fbm_for_warp(wx * freq, wz * freq, complexity, F32(roughness), seed + it * 101 + 1)
        wx += dx * amp * an
        wz += dz * amp * inv_an
        amp *= F32(attenuation)
        freq *= F32(2.0)
    return wx, wz