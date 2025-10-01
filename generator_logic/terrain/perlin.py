# generator_logic/terrain/perlin.py
from numba import njit, prange
import numpy as np
from game_engine_restructured.numerics.fast_noise import value_noise_2d, fbm_amplitude

from generator_logic.core.seeding import _resolve_world_seed, _mix_seed
from generator_logic.core.warp import apply_domain_warp

F32 = np.float32

@njit(cache=True, fastmath=True, parallel=True)
def generate_fbm_noise(
    coords_x, coords_z,
    noise_type_is_ridged, noise_type_is_billowy, octaves, gain, amplitude, seed, base_freq,
    use_warp, warp_freq,
    warp_amp0_m, warp_complexity, warp_roughness, warp_iterations, warp_attenuation, warp_anisotropy,
    warp_seed
):
    H, W = coords_x.shape
    output = np.empty((H, W), dtype=F32)

    for j in prange(H):
        for i in range(W):
            cx = F32(coords_x[j, i])
            cz = F32(coords_z[j, i])

            if use_warp:
                cx, cz = apply_domain_warp(
                    cx, cz,
                    base_freq_1pm=warp_freq,
                    amp0_m=warp_amp0_m,
                    complexity=warp_complexity,
                    roughness=warp_roughness,
                    iterations=warp_iterations,
                    attenuation=warp_attenuation,
                    anisotropy=warp_anisotropy,
                    seed=warp_seed
                )

            amp, freq, total = F32(1.0), F32(base_freq), F32(0.0)
            for o in range(octaves):
                n = F32(value_noise_2d(cx * freq, cz * freq, seed + o)) * F32(2.0) - F32(1.0)
                if noise_type_is_ridged:
                    n = F32(1.0) - np.abs(n)
                elif noise_type_is_billowy:
                    n = np.abs(n)
                total += n * amp
                freq *= F32(2.0)
                amp *= F32(gain)
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

    noise_type = noise_params.get('type', 'fbm').lower()
    wt = (warp_params.get('type', 'none') or 'none').lower()

    x = context['x_coords'].astype(np.float32)
    z = context['z_coords'].astype(np.float32)

    ANCHOR = np.float32(65536.0)
    base_x = np.floor(x[0, 0] / ANCHOR) * ANCHOR
    base_z = np.floor(z[0, 0] / ANCHOR) * ANCHOR
    x_local = x - base_x
    z_local = z - base_z
    
    node_off = int(noise_params.get('seed', 0))
    world_seed = _resolve_world_seed(context)
    seed_main  = _mix_seed(world_seed, node_off, 0)
    seed_warp  = _mix_seed(world_seed, node_off, 12345)

    # Параметры варпа
    warp_amp0_m = float(warp_params.get('amp0_m', 0.0))
    warp_freq = float(warp_params.get('frequency', 0.0))
    use_warp = (wt != 'none') and (warp_amp0_m > 0.0) and (warp_freq > 0.0)

    return generate_fbm_noise(
        x_local, z_local,
        noise_type_is_ridged=(noise_type == 'ridged'),
        noise_type_is_billowy=(noise_type == 'billowy'),
        octaves=int(noise_params.get('octaves', 8)),
        gain=np.float32(noise_params.get('gain', 0.5)),
        amplitude=np.float32(noise_params.get('amplitude', 1.0)),
        seed=seed_main,
        base_freq=np.float32(base_freq),

        # --- варп ---
        use_warp=use_warp,
        warp_freq=np.float32(warp_freq),
        warp_amp0_m=np.float32(warp_amp0_m),
        warp_complexity=int(warp_params.get('complexity', 1)),
        warp_roughness=np.float32(warp_params.get('roughness', 0.5)),
        warp_iterations=int(warp_params.get('iterations', 1)),
        warp_attenuation=np.float32(warp_params.get('attenuation', 1.0)),
        warp_anisotropy=np.float32(warp_params.get('anisotropy', 1.0)),
        warp_seed=seed_warp
    )
