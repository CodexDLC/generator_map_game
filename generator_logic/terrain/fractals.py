# generator_logic/terrain/fractals.py
from __future__ import annotations
import numpy as np
from numba import njit, prange
from game_engine_restructured.numerics.fast_noise import value_noise_2d, fbm_amplitude

# --- Основное Numba-ядро (теперь включает Warp) ---
@njit(cache=True, fastmath=True, parallel=True)
def _generate_multifractal_numba(
    coords_x, coords_z,
    # Fractal params
    noise_type_is_ridged, noise_type_is_billowy, octaves, roughness, seed,
    # Variation params
    var_strength, var_smoothness,
    # Position params
    offset_x, offset_y, scale_x, scale_y,
    # Warp params
    warp_type_is_simple, warp_type_is_complex, warp_freq, warp_amp, warp_octaves, warp_seed
):
    H, W = coords_x.shape
    output = np.empty((H, W), dtype=np.float32)

    # --- Главный цикл генерации по каждому пикселю ---
    for j in prange(H):
        for i in range(W):
            # 1. Применяем трансформации (Position) для текущего пикселя
            cx = (coords_x[j, i] + offset_x) * scale_x
            cz = (coords_z[j, i] + offset_y) * scale_y

            # 2. Применяем искажение (Warp) для текущего пикселя
            if warp_type_is_simple or warp_type_is_complex:
                local_offset_x = np.float32(0.0)
                local_offset_z = np.float32(0.0)
                if warp_type_is_simple:
                    local_offset_x = (value_noise_2d(cx * warp_freq, cz * warp_freq, warp_seed) * np.float32(2.0) - np.float32(1.0)) * warp_amp
                    local_offset_z = (value_noise_2d(cx * warp_freq, cz * warp_freq, warp_seed + 1) * np.float32(2.0) - np.float32(1.0)) * warp_amp
                elif warp_type_is_complex:
                    current_amp, current_freq = np.float32(warp_amp), np.float32(warp_freq)
                    for o in range(warp_octaves):
                        local_offset_x += (value_noise_2d(cx * current_freq, cz * current_freq, warp_seed + o) * np.float32(2.0) - np.float32(1.0)) * current_amp
                        local_offset_z += (value_noise_2d(cx * current_freq, cz * current_freq, warp_seed + o + 100) * np.float32(2.0) - np.float32(1.0)) * current_amp
                        current_freq *= np.float32(2.0)
                        current_amp *= np.float32(0.5)
                cx += local_offset_x
                cz += local_offset_z

            # 3. Рассчитываем MultiFractal для финальных (искаженных) координат
            variation_freq = np.float32(1.0) / (np.float32(2.0) ** (var_smoothness * np.float32(4.0)))
            local_variation = value_noise_2d(cx * variation_freq, cz * variation_freq, seed - 100)

            local_roughness = roughness * (np.float32(1.0) + (local_variation - np.float32(0.5)) * var_strength)
            local_roughness = max(np.float32(0.01), min(np.float32(0.99), local_roughness))

            amp, freq, total = np.float32(1.0), np.float32(1.0), np.float32(0.0)
            for o in range(octaves):
                n = value_noise_2d(cx * freq, cz * freq, seed + o) * np.float32(2.0) - np.float32(1.0)

                if noise_type_is_ridged: n = np.float32(1.0) - np.abs(n)
                elif noise_type_is_billowy: n = np.abs(n)

                total += n * amp
                freq *= np.float32(2.0)
                amp *= local_roughness

            output[j, i] = total

    # Нормализация (после цикла)
    max_amp = fbm_amplitude(roughness, octaves)
    if max_amp > 1e-6: output /= np.float32(max_amp)

    if not noise_type_is_ridged:
        output = (output + np.float32(1.0)) * np.float32(0.5)

    return np.clip(output, np.float32(0.0), np.float32(1.0))

# --- Python-обертка (остается без изменений) ---
def generate_multifractal(coords_x, coords_z, fractal_params: dict, variation_params: dict, position_params: dict, warp_params: dict):
    warp_type_str = warp_params.get('type', 'none')
    noise_type_str = fractal_params.get('type', 'fbm')

    # Явное приведение типов перед вызовом Numba-функции
    return _generate_multifractal_numba(
        coords_x.astype(np.float32), coords_z.astype(np.float32),
        # Fractal
        noise_type_is_ridged=noise_type_str == 'ridged',
        noise_type_is_billowy=noise_type_str == 'billowy',
        octaves=int(fractal_params.get('octaves', 8)),
        roughness=np.float32(fractal_params.get('roughness', 0.5)),
        seed=int(fractal_params.get('seed', 0)),
        # Variation
        var_strength=np.float32(variation_params.get('variation', 2.0)),
        var_smoothness=np.float32(variation_params.get('smoothness', 0.0)),
        # Position
        offset_x=np.float32(position_params.get('offset_x', 0.0)),
        offset_y=np.float32(position_params.get('offset_y', 0.0)),
        scale_x=np.float32(position_params.get('scale_x', 1.0)),
        scale_y=np.float32(position_params.get('scale_y', 1.0)),
        # Warp
        warp_type_is_simple=warp_type_str == 'simple',
        warp_type_is_complex=warp_type_str == 'complex',
        warp_freq=np.float32(warp_params.get('frequency', 0.05)),
        warp_amp=np.float32(warp_params.get('amplitude', 0.5)),
        warp_octaves=int(warp_params.get('octaves', 4)),
        warp_seed=int(warp_params.get('seed', 0))
    )