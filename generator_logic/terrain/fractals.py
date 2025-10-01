# generator_logic/terrain/fractals.py
from __future__ import annotations
import numpy as np
from numba import njit, prange
from game_engine_restructured.numerics.fast_noise import _hash2, fbm_amplitude
F32 = np.float32

@njit(inline='always', cache=True)
def _rand01_f32(ix: int, iz: int, seed: int) -> F32:
    return F32(_hash2(ix, iz, seed)) / F32(4294967296.0)

@njit(inline='always', cache=True)
def _fade_f32(t: F32) -> F32:
    return t * t * t * (t * (t * F32(6.0) - F32(15.0)) + F32(10.0))

@njit(inline='always', cache=True)
def _lerp_f32(a: F32, b: F32, t: F32) -> F32:
    return a + (b - a) * t

@njit(inline='always', cache=True)
def value_noise_2d_f32(x: F32, z: F32, seed: int) -> F32:
    xi, zi = int(np.floor(x)), int(np.floor(z))
    xf, zf = x - xi, z - zi
    u, v = _fade_f32(xf), _fade_f32(zf)
    n00 = _rand01_f32(xi, zi, seed)
    n10 = _rand01_f32(xi + 1, zi, seed)
    n01 = _rand01_f32(xi, zi + 1, seed)
    n11 = _rand01_f32(xi + 1, zi + 1, seed)
    nx0 = _lerp_f32(n00, n10, u)
    nx1 = _lerp_f32(n01, n11, u)
    return _lerp_f32(nx0, nx1, v)

@njit(cache=True, fastmath=True, parallel=True)
def _generate_multifractal_numba(
        coords_x, coords_z,
        noise_type_is_ridged, noise_type_is_billowy, octaves, roughness, seed, base_freq,
        var_strength, var_smoothness, var_contrast, var_damping, var_bias,
        offset_x, offset_y, scale_x, scale_y,
        warp_type_is_simple, warp_type_is_complex, warp_freq, warp_amp, warp_octaves, warp_seed
):
    H, W = coords_x.shape
    output = np.empty((H, W), dtype=F32)

    for j in prange(H):
        for i in range(W):
            cx = (coords_x[j, i] + offset_x) * scale_x
            cz = (coords_z[j, i] + offset_y) * scale_y

            if warp_type_is_simple or warp_type_is_complex:
                off_x, off_z = F32(0.0), F32(0.0)
                if warp_type_is_simple:
                    off_x = (value_noise_2d_f32(cx * warp_freq, cz * warp_freq, warp_seed) * F32(2.0) - F32(1.0)) * warp_amp
                    off_z = (value_noise_2d_f32(cx * warp_freq, cz * warp_freq, warp_seed + 1) * F32(2.0) - F32(1.0)) * warp_amp
                elif warp_type_is_complex:
                    amp_w, freq_w = F32(warp_amp), F32(warp_freq)
                    for o in range(warp_octaves):
                        off_x += (value_noise_2d_f32(cx * freq_w, cz * freq_w, warp_seed + o) * F32(2.0) - F32(1.0)) * amp_w
                        off_z += (value_noise_2d_f32(cx * freq_w, cz * freq_w, warp_seed + o + 100) * F32(2.0) - F32(1.0)) * amp_w
                        freq_w *= F32(2.0)
                        amp_w *= F32(0.5)
                cx += off_x
                cz += off_z

            var_freq = base_freq * (F32(2.0) ** -var_smoothness)
            local_var = value_noise_2d_f32(cx * var_freq, cz * var_freq, seed - 100)

            local_var = (local_var - F32(0.5)) * (F32(1.0) + var_contrast) + F32(0.5)
            local_var = local_var * (F32(1.0) - var_damping)
            local_var += var_bias - F32(0.5)
            local_var = max(F32(0.0), min(F32(1.0), local_var))

            var_influence = (local_var - F32(0.5)) * var_strength

            amp, freq, total = F32(1.0), F32(base_freq), F32(0.0)
            for o in range(octaves):
                n = value_noise_2d_f32(cx * freq, cz * freq, seed + o) * F32(2.0) - F32(1.0)
                if noise_type_is_ridged:
                    n = F32(1.0) - np.abs(n)
                elif noise_type_is_billowy:
                    n = np.abs(n)
                total += n * amp
                freq *= F32(2.0)
                amp *= roughness

            total = total * (F32(1.0) + var_influence)
            output[j, i] = total

    max_amp = fbm_amplitude(roughness, octaves)
    if max_amp > F32(1e-6): output /= F32(max_amp)
    if not noise_type_is_ridged: output = (output + F32(1.0)) * F32(0.5)
    return output

def multifractal_wrapper(context: dict, fractal_params: dict, variation_params: dict, position_params: dict,
                         warp_params: dict):
    world_size = context.get('WORLD_SIZE_METERS', 5000.0)
    relative_scale = float(fractal_params.get('scale', 0.5))
    scale_in_meters = relative_scale * world_size
    base_freq = 1.0 / (scale_in_meters + 1e-9)

    noise_type_str = fractal_params.get('type', 'fbm')
    warp_type_str = warp_params.get('type', 'none')

    var_strength = F32(variation_params.get('variation', 2.0))
    var_smoothness = F32(variation_params.get('smoothness', 0.0))
    var_contrast = F32(variation_params.get('contrast', 0.3))
    var_damping = F32(variation_params.get('damping', 0.25))
    var_bias = F32(variation_params.get('bias', 0.5))

    if var_smoothness < -20.0: var_smoothness = -20.0

    x = context['x_coords'].astype(F32)
    z = context['z_coords'].astype(F32)

    # --- Вызываем Numba-ядро, которое теперь возвращает "сырой" результат ---
    raw_output = _generate_multifractal_numba(
        x, z, # Используем оригинальные координаты
        noise_type_is_ridged=noise_type_str == 'ridged',
        noise_type_is_billowy=noise_type_str == 'billowy',
        octaves=int(fractal_params.get('octaves', 8)),
        roughness=F32(fractal_params.get('roughness', 0.5)),
        seed=int(fractal_params.get('seed', 0)),
        base_freq=F32(base_freq),
        var_strength=var_strength,
        var_smoothness=var_smoothness,
        var_contrast=var_contrast,
        var_damping=var_damping,
        var_bias=var_bias,
        # Параметры Position и Warp передаются как есть
        offset_x=F32(position_params.get('offset_x', 0.0)),
        offset_y=F32(position_params.get('offset_y', 0.0)),
        scale_x=F32(position_params.get('scale_x', 1.0)),
        scale_y=F32(position_params.get('scale_y', 1.0)),
        warp_type_is_simple=warp_type_str == 'simple',
        warp_type_is_complex=warp_type_str == 'complex',
        warp_freq=F32(warp_params.get('frequency', 0.05)),
        warp_amp=F32(warp_params.get('amplitude', 0.5)),
        warp_octaves=int(warp_params.get('octaves', 4)),
        warp_seed=int(fractal_params.get('seed', 0)) + 12345
    )

    # --- НАЧАЛО ИЗМЕНЕНИЯ: Финальное масштабирование результата ---
    # Находим фактический минимум и максимум в сгенерированных данных
    min_val = np.min(raw_output)
    max_val = np.max(raw_output)
    range_val = max_val - min_val

    # Растягиваем диапазон [min..max] до [0..1]
    if range_val > 1e-6:
        # Это стандартная формула нормализации
        normalized_output = (raw_output - min_val) / range_val
    else:
        # Если рельеф плоский, просто заполняем его средним значением
        normalized_output = np.full_like(raw_output, 0.5, dtype=F32)

    return normalized_output