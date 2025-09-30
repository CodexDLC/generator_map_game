# generator_logic/terrain/fractals.py
from __future__ import annotations
import numpy as np
from numba import njit, prange
from game_engine_restructured.numerics.fast_noise import _hash2, fbm_amplitude


# --- Внутренние helper-функции, переписанные для float32 ---

@njit(inline='always', cache=True)
def _rand01_f32(ix: int, iz: int, seed: int) -> np.float32:
    return np.float32(_hash2(ix, iz, seed)) / np.float32(4294967296.0)


@njit(inline='always', cache=True)
def _fade_f32(t: np.float32) -> np.float32:
    return t * t * t * (t * (t * np.float32(6.0) - np.float32(15.0)) + np.float32(10.0))


@njit(inline='always', cache=True)
def _lerp_f32(a: np.float32, b: np.float32, t: np.float32) -> np.float32:
    return a + (b - a) * t


@njit(inline='always', cache=True)
def value_noise_2d_f32(x: np.float32, z: np.float32, seed: int) -> np.float32:
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


# --- Основное Numba-ядро ---
@njit(cache=True, fastmath=True, parallel=True)
def _generate_multifractal_numba(
        coords_x, coords_z,
        noise_type_is_ridged, noise_type_is_billowy, octaves, roughness, seed, base_freq,
        var_strength, var_smoothness,
        offset_x, offset_y, scale_x, scale_y,
        warp_type_is_simple, warp_type_is_complex, warp_freq, warp_amp, warp_octaves, warp_seed
):
    H, W = coords_x.shape
    output = np.empty((H, W), dtype=np.float32)

    for j in prange(H):
        for i in range(W):
            cx = (coords_x[j, i] + offset_x) * scale_x
            cz = (coords_z[j, i] + offset_y) * scale_y

            if warp_type_is_simple or warp_type_is_complex:
                off_x, off_z = np.float32(0.0), np.float32(0.0)
                if warp_type_is_simple:
                    off_x = (value_noise_2d_f32(cx * warp_freq, cz * warp_freq, warp_seed) * np.float32(
                        2.0) - np.float32(1.0)) * warp_amp
                    off_z = (value_noise_2d_f32(cx * warp_freq, cz * warp_freq, warp_seed + 1) * np.float32(
                        2.0) - np.float32(1.0)) * warp_amp
                elif warp_type_is_complex:
                    amp_w, freq_w = np.float32(warp_amp), np.float32(warp_freq)
                    for o in range(warp_octaves):
                        off_x += (value_noise_2d_f32(cx * freq_w, cz * freq_w, warp_seed + o) * np.float32(
                            2.0) - np.float32(1.0)) * amp_w
                        off_z += (value_noise_2d_f32(cx * freq_w, cz * freq_w, warp_seed + o + 100) * np.float32(
                            2.0) - np.float32(1.0)) * amp_w
                        freq_w *= np.float32(2.0);
                        amp_w *= np.float32(0.5)
                cx += off_x;
                cz += off_z

            var_freq = base_freq * (np.float32(2.0) ** -var_smoothness)
            local_var = value_noise_2d_f32(cx * var_freq, cz * var_freq, seed - 100)
            local_roughness = roughness * (np.float32(1.0) + (local_var - np.float32(0.5)) * var_strength)
            local_roughness = max(np.float32(0.01), min(np.float32(0.99), local_roughness))

            amp, freq, total = np.float32(1.0), np.float32(base_freq), np.float32(0.0)
            for o in range(octaves):
                n = value_noise_2d_f32(cx * freq, cz * freq, seed + o) * np.float32(2.0) - np.float32(1.0)
                if noise_type_is_ridged:
                    n = np.float32(1.0) - np.abs(n)
                elif noise_type_is_billowy:
                    n = np.abs(n)
                total += n * amp
                freq *= np.float32(2.0);
                amp *= local_roughness
            output[j, i] = total

    max_amp = fbm_amplitude(roughness, octaves)
    if max_amp > 1e-6: output /= np.float32(max_amp)
    if not noise_type_is_ridged: output = (output + np.float32(1.0)) * np.float32(0.5)
    return np.clip(output, np.float32(0.0), np.float32(1.0))


# --- Python-обертка ---
def multifractal_wrapper(context: dict, fractal_params: dict, variation_params: dict, position_params: dict,
                         warp_params: dict):
    base_freq = 1.0 / (fractal_params.get('scale', 0.5) + 1e-9)
    noise_type_str = fractal_params.get('type', 'fbm')
    warp_type_str = warp_params.get('type', 'none')

    return _generate_multifractal_numba(
        context['x_coords'].astype(np.float32), context['z_coords'].astype(np.float32),
        noise_type_is_ridged=noise_type_str == 'ridged',
        noise_type_is_billowy=noise_type_str == 'billowy',
        octaves=int(fractal_params.get('octaves', 8)),
        roughness=np.float32(fractal_params.get('roughness', 0.5)),
        seed=int(fractal_params.get('seed', 0)),
        base_freq=np.float32(base_freq),
        var_strength=np.float32(variation_params.get('variation', 2.0)),
        var_smoothness=np.float32(variation_params.get('smoothness', 0.0)),
        offset_x=np.float32(position_params.get('offset_x', 0.0)),
        offset_y=np.float32(position_params.get('offset_y', 0.0)),
        scale_x=np.float32(position_params.get('scale_x', 1.0)),
        scale_y=np.float32(position_params.get('scale_y', 1.0)),
        warp_type_is_simple=warp_type_str == 'simple',
        warp_type_is_complex=warp_type_str == 'complex',
        warp_freq=np.float32(warp_params.get('frequency', 0.05)),
        warp_amp=np.float32(warp_params.get('amplitude', 0.5)),
        warp_octaves=int(warp_params.get('octaves', 4)),
        warp_seed=int(fractal_params.get('seed', 0)) + 12345
    )