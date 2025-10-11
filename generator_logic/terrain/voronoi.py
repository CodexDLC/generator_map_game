# generator_logic/terrain/voronoi.py
from numba import njit, prange
import numpy as np
# --- НАЧАЛО ИЗМЕНЕНИЯ ---
from game_engine_restructured.numerics.fast_noise_helpers import _hash2
# --- КОНЕЦ ИЗМЕНЕНИЯ ---

# Imports from core modules
from generator_logic.core.seeding import _resolve_world_seed, _mix_seed
from generator_logic.core.warp import apply_domain_warp

F32 = np.float32


# ---------- helpers (unique to voronoi) ----------
@njit(inline='always')
def _smoothstep01(t: F32) -> F32:
    if t < F32(0.0):
        t = F32(0.0)
    elif t > F32(1.0):
        t = F32(1.0)
    return t * t * (F32(3.0) - F32(2.0) * t)


@njit(inline='always')
def _soft_threshold01(x: F32, th: F32, width: F32) -> F32:
    e0 = th - width
    if e0 < F32(0.0): e0 = F32(0.0)
    if x <= e0: return F32(0.0)
    if x >= th: return x
    t = (x - e0) / (th - e0 + F32(1e-6))
    return x * _smoothstep01(t)


@njit(inline='always')
def _terrace01(x: F32, steps: int, blend: F32) -> F32:
    if steps <= 1: return x
    s = F32(steps)
    f = np.floor(x * s) / s
    c = np.ceil(x * s) / s
    t = (x - f) * s
    t = t * (F32(1.0) - blend) + _smoothstep01(t) * blend
    return f * (F32(1.0) - t) + c * t


@njit(inline='always')
def _dist(dx: F32, dz: F32, metric: int) -> F32:
    dx = np.abs(dx);
    dz = np.abs(dz)
    if metric == 1:  # Manhattan
        return dx + dz
    elif metric == 2:  # Chebyshev
        return dx if dx > dz else dz
    else:  # Euclidean
        return F32(np.sqrt(dx * dx + dz * dz))


# ---------- основное ядро ----------
@njit(cache=True, fastmath=True, parallel=True)
def generate_voronoi_noise(
        coords_x, coords_z,
        jitter, func_is_f1, func_is_f2, func_is_f2f1, gain, clamp_val, seed, base_freq,
        # варп-набор:
        use_warp,
        warp_freq, warp_amp0_m, warp_complexity, warp_roughness, warp_iterations, warp_attenuation, warp_anisotropy,
        warp_seed,
        # остальное:
        style_id, metric_id, terrace_steps, terrace_blend
):
    H, W = coords_x.shape
    out = np.empty((H, W), dtype=F32)

    inv_cell_norm_L2 = F32(1.0 / 0.70710678)
    inv_cell_norm_L1 = F32(1.0 / 1.0)
    inv_cell_norm_Li = F32(1.0 / 0.5)

    for j in prange(H):
        for i in range(W):
            cx = F32(coords_x[j, i])
            cz = F32(coords_z[j, i])

            if use_warp:
                cx, cz = apply_domain_warp(
                    cx, cz,
                    base_freq_1pm=F32(warp_freq),
                    amp0_m=F32(warp_amp0_m),
                    complexity=warp_complexity,
                    roughness=F32(warp_roughness),
                    iterations=warp_iterations,
                    attenuation=F32(warp_attenuation),
                    anisotropy=F32(warp_anisotropy),
                    seed=warp_seed
                )

            sx = cx * F32(base_freq)
            sz = cz * F32(base_freq)
            cell_x = int(np.floor(sx))
            cell_z = int(np.floor(sz))

            d1, d2 = F32(1e6), F32(1e6)
            for oz in range(-1, 2):
                for ox in range(-1, 2):
                    tx = cell_x + ox
                    tz = cell_z + oz
                    h = _hash2(tx, tz, seed)
                    rx = (F32(h & 0xFFFF) / F32(65535.0) - F32(0.5)) * F32(2.0) * F32(jitter)
                    rz = (F32(h >> 16) / F32(65535.0) - F32(0.5)) * F32(2.0) * F32(jitter)
                    px = F32(tx) + F32(0.5) + rx
                    pz = F32(tz) + F32(0.5) + rz

                    dist = _dist(px - sx, pz - sz, metric_id)

                    if dist < d1:
                        d2 = d1;
                        d1 = dist
                    elif dist < d2:
                        d2 = dist

            if metric_id == 1:
                inv_norm = inv_cell_norm_L1
            elif metric_id == 2:
                inv_norm = inv_cell_norm_Li
            else:
                inv_norm = inv_cell_norm_L2

            t1 = d1 * inv_norm * (F32(1.0) / (F32(gain) + F32(1e-9)))
            if t1 < F32(0.0): t1 = F32(0.0)
            if t1 > F32(1.0): t1 = F32(1.0)
            t2m1 = (d2 - d1) * (F32(1.0) / (F32(gain) + F32(1e-9)))
            if t2m1 < F32(0.0): t2m1 = F32(0.0)
            if t2m1 > F32(1.0): t2m1 = F32(1.0)

            # стили
            if style_id == 1:  # Ridges
                h = _smoothstep01(t2m1)
            elif style_id == 2:  # Peaks
                h = F32(1.0) - _smoothstep01(t1)
            elif style_id == 3:  # Plateaus
                base = F32(1.0) - _smoothstep01(t1)
                h = _terrace01(base, terrace_steps, F32(terrace_blend))
            elif style_id == 4:  # Mountains/Dual
                rid = _smoothstep01(t2m1)
                pk = F32(1.0) - _smoothstep01(t1)
                pk = pk * pk
                h = pk if pk > rid * F32(0.6) else rid * F32(0.6)
            else:  # Cells
                h = F32(1.0) - t1

            if clamp_val > F32(0.0):
                h = _soft_threshold01(h, F32(clamp_val), F32(0.1))

            out[j, i] = h

    return out


# ---------- wrapper ----------
def voronoi_noise_wrapper(context: dict, noise_params: dict, warp_params: dict):
    world_size = context.get('WORLD_SIZE_METERS', 5000.0)
    relative_scale = float(noise_params.get('scale', 0.5))
    scale_in_meters = relative_scale * world_size
    base_freq = np.float32(1.0 / (scale_in_meters + 1e-9))

    func_type = noise_params.get('function', 'f1').lower()
    wt = (warp_params.get('type', 'none') or 'none').lower()

    style_map = {'c': 0, 'cells': 0, 'r': 1, 'ridges': 1, 'p': 2, 'peaks': 2, 'a': 3, 'plateaus': 3, 'm': 4, 'd': 4,
                 'mountains': 4, 'dual': 4}
    metric_map = {'euclidean': 0, 'manhattan': 1, 'chebyshev': 2, 'cheby': 2}
    style_id = style_map.get(str(noise_params.get('style', 'd')).lower(), 4)
    metric_id = metric_map.get(str(noise_params.get('metric', 'euclidean')).lower(), 0)
    terr_steps = int(noise_params.get('terrace_steps', 8))
    terr_blend = np.float32(noise_params.get('terrace_blend', 0.35))

    x = context['x_coords'].astype(np.float32, copy=False)
    z = context['z_coords'].astype(np.float32, copy=False)

    ANCHOR = np.float32(65536.0)
    base_x = np.floor(x[0, 0] / ANCHOR) * ANCHOR
    base_z = np.floor(z[0, 0] / ANCHOR) * ANCHOR
    x_local = x - base_x
    z_local = z - base_z

    node_off = int(noise_params.get('seed', 0))
    world_seed = _resolve_world_seed(context)
    seed_main = _mix_seed(world_seed, node_off, 0)
    seed_warp = _mix_seed(world_seed, node_off, 12345)

    # Параметры варпа
    warp_amp0_m = float(warp_params.get('amp0_m', 0.0))
    warp_freq = float(warp_params.get('frequency', 0.0))
    use_warp = (wt != 'none') and (warp_amp0_m > 0.0) and (warp_freq > 0.0)
    is_simple = (wt == 'simple')

    return generate_voronoi_noise(
        x_local, z_local,
        jitter=np.float32(noise_params.get('jitter', 0.45)),
        func_is_f1=(func_type == 'f1'),
        func_is_f2=(func_type == 'f2'),
        func_is_f2f1=(func_type == 'f2-f1'),
        gain=np.float32(noise_params.get('gain', 0.5)),
        clamp_val=np.float32(noise_params.get('clamp', 0.0)),
        seed=seed_main,
        base_freq=base_freq,

        # варп:
        use_warp=use_warp,
        warp_freq=np.float32(warp_freq),
        warp_amp0_m=np.float32(warp_amp0_m),
        warp_complexity=1 if is_simple else int(warp_params.get('complexity', 1)),
        warp_roughness=0.5 if is_simple else np.float32(warp_params.get('roughness', 0.5)),
        warp_iterations=1 if is_simple else int(warp_params.get('iterations', 1)),
        warp_attenuation=1.0 if is_simple else np.float32(warp_params.get('attenuation', 1.0)),
        warp_anisotropy=1.0 if is_simple else np.float32(warp_params.get('anisotropy', 1.0)),
        warp_seed=seed_warp,

        style_id=style_id, metric_id=metric_id,
        terrace_steps=terr_steps, terrace_blend=terr_blend
    )