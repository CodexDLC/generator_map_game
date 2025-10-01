from numba import njit, prange
import numpy as np
from game_engine_restructured.numerics.fast_noise import value_noise_2d, fbm_amplitude

F32 = np.float32


@njit(cache=True, fastmath=True, parallel=True)
def generate_fbm_noise(
    coords_x, coords_z,
    noise_type_is_ridged, noise_type_is_billowy, octaves, gain, amplitude, seed, base_freq,
    warp_type_is_simple, warp_type_is_complex, warp_freq, warp_amp, warp_octaves, warp_seed
):
    H, W = coords_x.shape
    output = np.empty((H, W), dtype=F32)

    for j in prange(H):
        for i in range(W):
            cx = F32(coords_x[j, i])
            cz = F32(coords_z[j, i])

            # --- warp ---
            if warp_type_is_simple or warp_type_is_complex:
                ox, oz = F32(0.0), F32(0.0)
                if warp_type_is_simple:
                    ox = (F32(value_noise_2d(cx * warp_freq, cz * warp_freq, warp_seed)) * F32(2.0) - F32(1.0)) * F32(warp_amp)
                    oz = (F32(value_noise_2d(cx * warp_freq, cz * warp_freq, warp_seed + 1)) * F32(2.0) - F32(1.0)) * F32(warp_amp)
                else:
                    amp_w, freq_w = F32(warp_amp), F32(warp_freq)
                    for o in range(warp_octaves):
                        ox += (F32(value_noise_2d(cx * freq_w, cz * freq_w, warp_seed + o)) * F32(2.0) - F32(1.0)) * amp_w
                        oz += (F32(value_noise_2d(cx * freq_w, cz * freq_w, warp_seed + o + 100)) * F32(2.0) - F32(1.0)) * amp_w
                        freq_w *= F32(2.0)
                        amp_w  *= F32(0.5)
                cx += ox; cz += oz

            # --- fBm ---
            amp, freq, total = F32(1.0), F32(base_freq), F32(0.0)
            for o in range(octaves):
                n = F32(value_noise_2d(cx * freq, cz * freq, seed + o)) * F32(2.0) - F32(1.0)
                if noise_type_is_ridged:
                    n = F32(1.0) - np.abs(n)
                elif noise_type_is_billowy:
                    n = np.abs(n)
                total += n * amp
                freq *= F32(2.0)
                amp  *= F32(gain)
            output[j, i] = total

    max_amp = F32(fbm_amplitude(F32(gain), octaves))
    if max_amp > F32(1e-6):
        output /= max_amp

    if not noise_type_is_ridged:
        output = (output + F32(1.0)) * F32(0.5)

    return np.clip(output * F32(amplitude), F32(0.0), F32(1.0))


def fbm_noise_wrapper(context: dict, noise_params: dict, warp_params: dict):
    world_size = context.get('WORLD_SIZE_METERS', 5000.0)
    relative_scale = float(noise_params.get('scale', 0.5))
    scale_in_meters = relative_scale * world_size
    base_freq = 1.0 / (scale_in_meters + 1e-9)

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
        base_freq=np.float32(base_freq),
        warp_type_is_simple=warp_type == 'simple',
        warp_type_is_complex=warp_type == 'complex',
        warp_freq=np.float32(warp_params.get('frequency', 0.05)),
        warp_amp=np.float32(warp_params.get('amplitude', 0.5)),
        warp_octaves=int(warp_params.get('octaves', 4)),
        warp_seed=int(noise_params.get('seed', 0)) + 12345
    )
