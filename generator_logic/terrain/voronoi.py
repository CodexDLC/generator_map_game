from numba import njit, prange
import numpy as np
from game_engine_restructured.numerics.fast_noise import value_noise_2d, _hash2

F32 = np.float32


# ---- helpers (numba-friendly) ----
@njit(inline='always')
def _smoothstep01(t: F32) -> F32:
    if t < F32(0.0): t = F32(0.0)
    elif t > F32(1.0): t = F32(1.0)
    return t * t * (F32(3.0) - F32(2.0) * t)

@njit(inline='always')
def _soft_threshold01(x: F32, th: F32, width: F32) -> F32:
    # плавный порог: 0 до (th-width), 1 после th, s-образный переход
    e0 = th - width
    if e0 < F32(0.0): e0 = F32(0.0)
    if x <= e0: return F32(0.0)
    if x >= th: return x
    t = (x - e0) / (th - e0 + F32(1e-6))
    return x * _smoothstep01(t)

@njit(inline='always')
def _terrace01(x: F32, steps: int, blend: F32) -> F32:
    # террасы: к ближайшей ступени с небольшим сглаживанием
    if steps <= 1: return x
    s = F32(steps)
    f = np.floor(x * s) / s
    c = np.ceil (x * s) / s
    t = (x - f) * s
    t = t * (F32(1.0) - blend) + _smoothstep01(t) * blend
    return f * (F32(1.0) - t) + c * t

# metric: 0=euclid, 1=manhattan, 2=chebyshev
@njit(inline='always')
def _dist(dx: F32, dz: F32, metric: int) -> F32:
    dx = np.abs(dx); dz = np.abs(dz)
    if metric == 1:
        return dx + dz           # L1
    elif metric == 2:
        return dx if dx > dz else dz  # L∞
    else:
        return F32(np.sqrt(dx*dx + dz*dz))  # L2


@njit(cache=True, fastmath=True, parallel=True)
def generate_voronoi_noise(
    coords_x, coords_z,
    jitter, func_is_f1, func_is_f2, func_is_f2f1, gain, clamp_val, seed, base_freq,
    warp_type_is_simple, warp_type_is_complex, warp_freq, warp_amp, warp_octaves, warp_seed,
    style_id, metric_id,    # NEW: style (0:cells,1:ridges,2:peaks,3:plateaus,4:mountains), metric (0/1/2)
    terrace_steps, terrace_blend  # для plateaus
):
    H, W = coords_x.shape
    out = np.empty((H, W), dtype=F32)

    # нормировка радиуса клетки: для L2 максимум внутри клетки ≈ sqrt(0.5^2+0.5^2)=0.7071
    inv_cell_norm_L2 = F32(1.0 / 0.70710678)
    inv_cell_norm_L1 = F32(1.0 / 1.0)        # max в L1 на половине клетки = 1.0
    inv_cell_norm_Li = F32(1.0 / 0.5)        # max в L∞ на половине клетки = 0.5

    for j in prange(H):
        for i in range(W):
            cx = F32(coords_x[j, i]); cz = F32(coords_z[j, i])

            # --- warp (как у тебя) ---
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
                        freq_w *= F32(2.0); amp_w *= F32(0.5)
                cx += ox; cz += oz

            # клетка
            sx = cx * F32(base_freq)
            sz = cz * F32(base_freq)
            cell_x = int(np.floor(sx)); cell_z = int(np.floor(sz))

            d1, d2 = F32(1e6), F32(1e6)
            for oz in range(-1, 2):
                for ox in range(-1, 2):
                    tx = cell_x + ox; tz = cell_z + oz
                    h  = _hash2(tx, tz, seed)
                    rx = (F32(h & 0xFFFF) / F32(65535.0) - F32(0.5)) * F32(2.0) * F32(jitter)
                    rz = (F32(h >> 16)    / F32(65535.0) - F32(0.5)) * F32(2.0) * F32(jitter)
                    px = F32(tx) + F32(0.5) + rx
                    pz = F32(tz) + F32(0.5) + rz

                    dist = _dist(px - sx, pz - sz, metric_id)

                    if dist < d1:
                        d2 = d1; d1 = dist
                    elif dist < d2:
                        d2 = dist

            # нормировки под разные метрики
            if metric_id == 1: inv_norm = inv_cell_norm_L1
            elif metric_id == 2: inv_norm = inv_cell_norm_Li
            else: inv_norm = inv_cell_norm_L2

            # базовые поля
            t1 = d1 * inv_norm * (F32(1.0) / (F32(gain) + F32(1e-9)))  # [0..~1]
            if t1 < F32(0.0): t1 = F32(0.0)
            if t1 > F32(1.0): t1 = F32(1.0)
            t2m1 = (d2 - d1) * (F32(1.0) / (F32(gain) + F32(1e-9)))
            if t2m1 < F32(0.0): t2m1 = F32(0.0)
            if t2m1 > F32(1.0): t2m1 = F32(1.0)

            # стили
            if style_id == 1:          # ridges
                h = _smoothstep01(t2m1)
            elif style_id == 2:        # peaks
                h = F32(1.0) - _smoothstep01(t1)
            elif style_id == 3:        # plateaus
                base = F32(1.0) - _smoothstep01(t1)
                h = _terrace01(base, terrace_steps, F32(terrace_blend))
            elif style_id == 4:        # mountains = mix peaks & ridges
                rid = _smoothstep01(t2m1)
                pk  = F32(1.0) - _smoothstep01(t1)
                # чуть заостряем вершины
                pk = pk * pk
                h = pk if pk > rid * F32(0.6) else rid * F32(0.6)
            else:                       # cells
                h = F32(1.0) - t1

            # мягкий порог
            if clamp_val > F32(0.0):
                h = _soft_threshold01(h, F32(clamp_val), F32(0.1))

            out[j, i] = h

    return out


def voronoi_noise_wrapper(context: dict, noise_params: dict, warp_params: dict):
    world_size = context.get('WORLD_SIZE_METERS', 5000.0)
    relative_scale = float(noise_params.get('scale', 0.5))
    scale_in_meters = relative_scale * world_size
    base_freq = np.float32(1.0 / (scale_in_meters + 1e-9))

    func_type = noise_params.get('function', 'f1').lower()
    warp_type = warp_params.get('type', 'none').lower()

    # NEW: стиль и метрика
    style_map  = {'c':0,'cells':0,'r':1,'ridges':1,'p':2,'peaks':2,'a':3,'plateaus':3,'m':4,'d':4,'mountains':4,'dual':4}
    metric_map = {'euclidean':0, 'manhattan':1, 'chebyshev':2, 'cheby':2}

    style_id   = style_map.get(str(noise_params.get('style','d')).lower(), 4)
    metric_id  = metric_map.get(str(noise_params.get('metric','euclidean')).lower(), 0)
    terr_steps = int(noise_params.get('terrace_steps', 8))
    terr_blend = np.float32(noise_params.get('terrace_blend', 0.35))

    x = context['x_coords'].astype(np.float32, copy=False)
    z = context['z_coords'].astype(np.float32, copy=False)

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
        clamp_val=np.float32(noise_params.get('clamp', 0.0)),
        seed=int(noise_params.get('seed', 0)),
        base_freq=base_freq,
        warp_type_is_simple=warp_type == 'simple',
        warp_type_is_complex=warp_type == 'complex',
        warp_freq=np.float32(warp_params.get('frequency', 0.05)),
        warp_amp=np.float32(warp_params.get('amplitude', 0.5)),
        warp_octaves=int(warp_params.get('octaves', 14)),
        warp_seed=int(noise_params.get('seed', 0)) + 12345,
        style_id=style_id, metric_id=metric_id,
        terrace_steps=terr_steps, terrace_blend=terr_blend
    )
