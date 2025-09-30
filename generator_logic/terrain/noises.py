# generator_logic/terrain/noises.py
from __future__ import annotations
import numpy as np
from numba import njit, prange
from game_engine_restructured.numerics.fast_noise import value_noise_2d, fbm_amplitude, _hash2

F32 = np.float32


@njit(cache=True, fastmath=True, parallel=True)
def generate_fbm_noise(
        coords_x, coords_z,
        # Noise params
        noise_type_is_ridged, noise_type_is_billowy, octaves, gain, amplitude, seed, base_freq,
        # Warp params
        warp_type_is_simple, warp_type_is_complex, warp_freq, warp_amp, warp_octaves, warp_seed
):
    H, W = coords_x.shape
    output = np.empty((H, W), dtype=F32)

    for j in prange(H):
        for i in range(W):
            cx, cz = coords_x[j, i], coords_z[j, i]

            # Warp logic inside the loop
            if warp_type_is_simple or warp_type_is_complex:
                offset_x, offset_z = F32(0.0), F32(0.0)
                if warp_type_is_simple:
                    offset_x = (value_noise_2d(cx * warp_freq, cz * warp_freq, warp_seed) * F32(2.0) - F32(1.0)) * warp_amp
                    offset_z = (value_noise_2d(cx * warp_freq, cz * warp_freq, warp_seed + 1) * F32(2.0) - F32(1.0)) * warp_amp
                elif warp_type_is_complex:
                    amp_w, freq_w = F32(warp_amp), F32(warp_freq)
                    for o in range(warp_octaves):
                        offset_x += (value_noise_2d(cx * freq_w, cz * freq_w, warp_seed + o) * F32(2.0) - F32(1.0)) * amp_w
                        offset_z += (value_noise_2d(cx * freq_w, cz * freq_w, warp_seed + o + 100) * F32(2.0) - F32(1.0)) * amp_w
                        freq_w *= F32(2.0)
                        amp_w *= F32(0.5)
                cx += offset_x
                cz += offset_z

            # FBM logic
            amp, freq, total = F32(1.0), F32(base_freq), F32(0.0)
            for o in range(octaves):
                n = value_noise_2d(cx * freq, cz * freq, seed + o) * F32(2.0) - F32(1.0)
                if noise_type_is_ridged:
                    n = F32(1.0) - np.abs(n)
                elif noise_type_is_billowy:
                    n = np.abs(n)
                total += n * amp
                freq *= F32(2.0)
                amp *= gain
            output[j, i] = total

    max_amp = fbm_amplitude(gain, octaves)
    if max_amp > F32(1e-6): output /= F32(max_amp)

    if not noise_type_is_ridged:
        output = (output + F32(1.0)) * F32(0.5)

    return np.clip(output * amplitude, F32(0.0), F32(1.0))


@njit(cache=True, fastmath=True, parallel=True)
def generate_voronoi_noise(
        coords_x, coords_z,
        jitter, func_is_f1, func_is_f2, func_is_f2f1, gain, clamp_val, seed,
        warp_type_is_simple, warp_type_is_complex, warp_freq, warp_amp, warp_octaves, warp_seed
):
    H, W = coords_x.shape
    output = np.empty((H, W), dtype=F32)

    for j in prange(H):
        for i in range(W):
            cx, cz = coords_x[j, i], coords_z[j, i]

            if warp_type_is_simple or warp_type_is_complex:
                offset_x, offset_z = F32(0.0), F32(0.0)
                if warp_type_is_simple:
                    offset_x = (value_noise_2d(cx * warp_freq, cz * warp_freq, warp_seed) * F32(2.0) - F32(1.0)) * warp_amp
                    offset_z = (value_noise_2d(cx * warp_freq, cz * warp_freq, warp_seed + 1) * F32(2.0) - F32(1.0)) * warp_amp
                elif warp_type_is_complex:
                    amp_w, freq_w = F32(warp_amp), F32(warp_freq)
                    for o in range(warp_octaves):
                        offset_x += (value_noise_2d(cx * freq_w, cz * freq_w, warp_seed + o) * F32(2.0) - F32(1.0)) * amp_w
                        offset_z += (value_noise_2d(cx * freq_w, cz * freq_w, warp_seed + o + 100) * F32(2.0) - F32(1.0)) * amp_w
                        freq_w *= F32(2.0)
                        amp_w *= F32(0.5)
                cx += offset_x
                cz += offset_z

            cell_x, cell_z = int(np.floor(cx)), int(np.floor(cz))
            min_dist1, min_dist2 = F32(1e6), F32(1e6)

            for oz in range(-1, 2):
                for ox in range(-1, 2):
                    test_cell_x, test_cell_z = cell_x + ox, cell_z + oz
                    point_hash = _hash2(test_cell_x, test_cell_z, seed)
                    rand_x = (point_hash & 0xFFFF) / 65535.0 * jitter
                    rand_z = (point_hash >> 16) / 65535.0 * jitter
                    point_x = test_cell_x + rand_x
                    point_z = test_cell_z + rand_z
                    dist = np.sqrt((point_x - cx) ** 2 + (point_z - cz) ** 2)

                    if dist < min_dist1:
                        min_dist2, min_dist1 = min_dist1, dist
                    elif dist < min_dist2:
                        min_dist2 = dist

            if func_is_f1:
                val = min_dist1
            elif func_is_f2:
                val = min_dist2
            elif func_is_f2f1:
                val = min_dist2 - min_dist1
            else:
                val = min_dist1

            output[j, i] = val

    output = F32(1.0) - np.clip(output * (F32(1.0) / (gain + F32(1e-9))), F32(0.0), F32(1.0))
    if clamp_val > 0:
        output = np.where(output < clamp_val, F32(0.0), output)

    return output


def fbm_noise_wrapper(context: dict, noise_params: dict, warp_params: dict):
    noise_type = noise_params.get('type', 'fbm')
    warp_type = warp_params.get('type', 'none')

    x = context['x_coords'].astype(np.float32)
    z = context['z_coords'].astype(np.float32)

    ANCHOR = np.float32(65536.0)
    base_x = np.floor(x[0, 0] / ANCHOR) * ANCHOR
    base_z = np.floor(z[0, 0] / ANCHOR) * ANCHOR

    x_local = x - base_x
    z_local = z - base_z

    return generate_fbm_noise(
        x_local, z_local,
        noise_type_is_ridged=noise_type == 'ridged',
        noise_type_is_billowy=noise_type == 'billowy',
        octaves=int(noise_params.get('octaves', 8)),
        gain=np.float32(noise_params.get('gain', 0.5)),
        amplitude=np.float32(noise_params.get('amplitude', 1.0)),
        seed=int(noise_params.get('seed', 0)),
        base_freq=np.float32(1.0 / (noise_params.get('scale', 0.5) + 1e-9)),
        warp_type_is_simple=warp_type == 'simple',
        warp_type_is_complex=warp_type == 'complex',
        warp_freq=np.float32(warp_params.get('frequency', 0.05)),
        warp_amp=np.float32(warp_params.get('amplitude', 0.5)),
        warp_octaves=int(warp_params.get('octaves', 4)),
        warp_seed=int(warp_params.get('seed', 0)) + 12345
    )


def voronoi_noise_wrapper(context: dict, noise_params: dict, warp_params: dict):
    func_type = noise_params.get('function', 'f1')
    warp_type = warp_params.get('type', 'none')

    x = context['x_coords'].astype(np.float32)
    z = context['z_coords'].astype(np.float32)

    x = x * np.float32(noise_params.get('scale', 0.5) * 100)
    z = z * np.float32(noise_params.get('scale', 0.5) * 100)

    ANCHOR = np.float32(65536.0)
    base_x = np.floor(x[0, 0] / ANCHOR) * ANCHOR
    base_z = np.floor(z[0, 0] / ANCHOR) * ANCHOR

    x_local = x - base_x
    z_local = z - base_z

    return generate_voronoi_noise(
        x_local, z_local,
        jitter=np.float32(noise_params.get('jitter', 0.45)),
        func_is_f1=func_type == 'f1',
        func_is_f2=func_type == 'f2',
        func_is_f2f1=func_type == 'f2-f1',
        gain=np.float32(noise_params.get('gain', 0.5)),
        clamp_val=np.float32(noise_params.get('clamp', 0.5)),
        seed=int(noise_params.get('seed', 0)),
        warp_type_is_simple=warp_type == 'simple',
        warp_type_is_complex=warp_type == 'complex',
        warp_freq=np.float32(warp_params.get('frequency', 0.05)),
        warp_amp=np.float32(warp_params.get('amplitude', 0.5)),
        warp_octaves=int(warp_params.get('octaves', 4)),
        warp_seed=int(warp_params.get('seed', 0)) + 12345
    )
