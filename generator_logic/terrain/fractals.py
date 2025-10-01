# generator_logic/terrain/fractals.py
from __future__ import annotations
import numpy as np
from numba import njit, prange

from game_engine_restructured.numerics.fast_noise import value_noise_2d
from ..core.normalization import normalize01

F32 = np.float32


# ======================================================================
# ШАГ 1: Numba-ядро, теперь с корректной передачей сида
# ======================================================================

@njit(cache=True, fastmath=True)
def _fbm_numba(noise_fn, u, v, octaves, roughness, seed):
    amp = F32(1.0)
    freq = F32(1.0)
    value = F32(0.0)
    norm = F32(0.0)
    for i in range(octaves):
        # --- ИСПРАВЛЕНИЕ: Используем seed + номер октавы ---
        noise_val = noise_fn(u * freq, v * freq, seed + i) * F32(2.0) - F32(1.0)
        value += amp * noise_val
        norm += amp
        amp *= roughness
        freq *= F32(2.0)
    if norm < 1e-6:
        return F32(0.0)
    return value / norm


@njit(cache=True, fastmath=True, parallel=True)
def _generate_fractal_kernel(
        out_array, u_coords, v_coords, seed,
        ntype_is_ridged, ntype_is_billowy,
        octaves, roughness,
        use_warp, wfreq, wamp, woct
):
    H, W = out_array.shape

    for j in prange(H):
        for i in range(W):
            u = u_coords[j, i]
            v = v_coords[j, i]

            if use_warp:
                # --- ИСПРАВЛЕНИЕ: Передаем сиды в Domain Warp ---
                warp_seed = seed + 777
                dx = _fbm_numba(value_noise_2d, u * wfreq, v * wfreq, woct, roughness, warp_seed)
                dy = _fbm_numba(value_noise_2d, (u + F32(37.17)) * wfreq, (v - F32(11.41)) * wfreq, woct, roughness,
                                warp_seed + 1)
                u += wamp * dx
                v += wamp * dy

            # --- ИСПРАВЛЕНИЕ: Передаем основной сид в генерацию фрактала ---
            fbm_val = _fbm_numba(value_noise_2d, u, v, octaves, roughness, seed)

            if ntype_is_ridged:
                result = F32(1.0) - np.abs(fbm_val)
            elif ntype_is_billowy:
                result = np.abs(fbm_val)
            else:  # FBM
                result = fbm_val

            out_array[j, i] = result


# ======================================================================
# ШАГ 2: Главная функция-обертка (без изменений)
# ======================================================================

def multifractal_wrapper(context: dict, fractal_params: dict, variation_params: dict, position_params: dict,
                         warp_params: dict):
    x_coords = context['x_coords']
    z_coords = context['z_coords']
    H, W = x_coords.shape

    seed = int(fractal_params.get('seed', 0))
    ntype = (fractal_params.get('type', 'fbm') or 'fbm').lower()
    octaves = max(1, min(int(fractal_params.get('octaves', 8)), 16))
    roughness = F32(fractal_params.get('roughness', 0.5))
    base_scale = max(float(fractal_params.get('scale', 0.5)), 1e-5)

    ox = float(position_params.get('offset_x', 0.0))
    oy = float(position_params.get('offset_y', 0.0))
    sx = float(position_params.get('scale_x', 1.0)) or 1.0
    sy = float(position_params.get('scale_y', 1.0)) or 1.0

    wtype = (warp_params.get('type', 'none') or 'none').lower()
    wfreq = F32(warp_params.get('frequency', 0.0))
    wamp = F32(warp_params.get('amplitude', 0.0))
    woct = max(1, min(int(warp_params.get('octaves', 4)), 16))

    var = float(variation_params.get('variation', 1.0))
    smooth = float(variation_params.get('smoothness', 0.0))
    contrast = float(variation_params.get('contrast', 0.0))
    damping = float(variation_params.get('damping', 0.0))
    bias = float(variation_params.get('bias', 0.0))

    u = (x_coords * sx + ox) / (context['WORLD_SIZE_METERS'] * base_scale)
    v = (z_coords * sy + oy) / (context['WORLD_SIZE_METERS'] * base_scale)

    output_array = np.empty((H, W), dtype=F32)

    _generate_fractal_kernel(
        output_array, u.astype(F32), v.astype(F32), seed,
        ntype.startswith('rid'), ntype.startswith('bil'),
        octaves, roughness,
        wtype != 'none' and wamp > 0, wfreq, wamp, woct
    )

    f = output_array

    if damping > 0:
        low_freq_output = np.empty_like(f)
        _generate_fractal_kernel(
            low_freq_output, (u * 0.5).astype(F32), (v * 0.5).astype(F32), seed,
            ntype.startswith('rid'), ntype.startswith('bil'),
            max(octaves // 2, 1), roughness, False, 0, 0, 0
        )
        f = normalize01(f, mode='minmax')
        low = normalize01(low_freq_output, mode='minmax')
        f = (1.0 - damping) * f + damping * low

    f = normalize01(f, mode='minmax')

    if smooth > 0:
        f = np.power(f, 1.0 + smooth)

    if contrast != 0:
        m = np.mean(f)
        f = np.clip((f - m) * (1.0 + np.clip(contrast, 0.0, 1.0) * 2.0) + m, 0.0, 1.0)

    if bias != 0:
        f = f + bias * 0.25
        f = normalize01(f, mode='minmax')

    if var != 1.0:
        m = f.mean()
        f = np.clip(m + (f - m) * var, 0.0, 1.0)

    return f.astype(np.float32)