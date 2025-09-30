# generator_logic/terrain/noises.py
from __future__ import annotations
import numpy as np
from numba import njit, prange
from game_engine_restructured.numerics.fast_noise import (
    _hash2, _rand01, _fade, _lerp, value_noise_2d, fbm_amplitude
)

# --- Общая логика для Warp (искажения) ---
@njit(cache=True, fastmath=True)
def apply_warp(coords_x, coords_z, warp_params: dict):
    warp_type = warp_params.get('type', 'none')
    if warp_type == 'none':
        return coords_x, coords_z

    amp = warp_params.get('amplitude', 0.5) * 200 # Примерный перевод 0..1 в масштаб
    freq = warp_params.get('frequency', 0.05) / 20 # Примерный перевод 0..1 в частоту
    octaves = warp_params.get('octaves', 4)
    seed = warp_params.get('seed', 0)

    offset_x = np.zeros_like(coords_x)
    offset_z = np.zeros_like(coords_z)

    # Простой варп - одна октава
    if warp_type == 'simple':
        offset_x = (value_noise_2d(coords_x * freq, coords_z * freq, seed) * 2.0 - 1.0) * amp
        offset_z = (value_noise_2d(coords_x * freq, coords_z * freq, seed + 1) * 2.0 - 1.0) * amp

    # Комплексный варп - FBM
    elif warp_type == 'complex':
        current_amp = amp
        current_freq = freq
        for o in range(octaves):
            offset_x += (value_noise_2d(coords_x * current_freq, coords_z * current_freq, seed + o) * 2.0 - 1.0) * current_amp
            offset_z += (value_noise_2d(coords_x * current_freq, coords_z * current_freq, seed + o + 100) * 2.0 - 1.0) * current_amp
            current_freq *= 2.0
            current_amp *= 0.5

    return coords_x + offset_x, coords_z + offset_z

# --- Логика для Perlin/FBM ноды ---
@njit(cache=True, fastmath=True, parallel=True)
def generate_fbm_noise(coords_x, coords_z, noise_params: dict, warp_params: dict):
    warped_x, warped_z = apply_warp(coords_x, coords_z, warp_params)

    noise_type = noise_params.get('type', 'fbm')
    octaves = noise_params.get('octaves', 8)
    gain = noise_params.get('gain', 0.5)
    height = noise_params.get('height', 1.0)
    seed = noise_params.get('seed', 0)

    H, W = warped_x.shape
    output = np.empty((H, W), dtype=np.float32)

    for j in prange(H):
        for i in range(W):
            cx, cz = warped_x[j, i], warped_z[j, i]
            amp, freq, total = 1.0, 1.0, 0.0

            for o in range(octaves):
                n = value_noise_2d(cx * freq, cz * freq, seed + o) * 2.0 - 1.0 # -> [-1, 1]

                if noise_type == 'ridged':
                    n = 1.0 - np.abs(n)
                elif noise_type == 'billowy':
                    n = np.abs(n)

                total += n * amp
                freq *= 2.0 # Lacunarity = 2
                amp *= gain

            output[j, i] = total

    max_amp = fbm_amplitude(gain, octaves)
    if max_amp > 1e-6: output /= max_amp

    # FBM/Billowy в [0,1], Ridged остается в [0,1]
    if noise_type != 'ridged':
        output = (output + 1.0) * 0.5

    return np.clip(output * height, 0.0, 1.0)

# --- Логика для Voronoi ноды (новая, быстрая) ---
@njit(cache=True, fastmath=True, parallel=True)
def generate_voronoi_noise(coords_x, coords_z, noise_params: dict, warp_params: dict):
    warped_x, warped_z = apply_warp(coords_x, coords_z, warp_params)

    jitter = noise_params.get('jitter', 0.45)
    func = noise_params.get('function', 'f1')
    gain = noise_params.get('gain', 0.5)
    clamp_val = noise_params.get('clamp', 0.5)
    seed = noise_params.get('seed', 0)

    H, W = warped_x.shape
    output = np.empty((H, W), dtype=np.float32)

    for j in prange(H):
        for i in range(W):
            cx, cz = warped_x[j, i], warped_z[j, i]

            cell_x, cell_z = int(np.floor(cx)), int(np.floor(cz))

            min_dist1 = 1e6
            min_dist2 = 1e6

            for oz in range(-1, 2):
                for ox in range(-1, 2):
                    test_cell_x, test_cell_z = cell_x + ox, cell_z + oz

                    point_hash = _hash2(test_cell_x, test_cell_z, seed)
                    rand_x = (point_hash & 0xFFFF) / 0xFFFF * jitter
                    rand_z = (point_hash >> 16) / 0xFFFF * jitter

                    point_x = test_cell_x + rand_x
                    point_z = test_cell_z + rand_z

                    dist = np.sqrt((point_x - cx)**2 + (point_z - cz)**2)

                    if dist < min_dist1:
                        min_dist2 = min_dist1
                        min_dist1 = dist
                    elif dist < min_dist2:
                        min_dist2 = dist

            if func == 'f1':
                val = min_dist1
            elif func == 'f2':
                val = min_dist2
            elif func == 'f2-f1':
                val = min_dist2 - min_dist1
            else: # fallback to f1
                val = min_dist1

            output[j, i] = val

    # Постобработка
    output = 1.0 - np.clip(output * (1.0 / (gain + 1e-9)), 0.0, 1.0)
    if clamp_val > 0:
        output = np.where(output < clamp_val, 0.0, output)

    return output
