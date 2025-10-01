# generator_logic/terrain/fractals.py
from __future__ import annotations
import numpy as np
from numba import njit, prange

from game_engine_restructured.numerics.fast_noise import value_noise_2d
from generator_logic.core.normalization import normalize01
from generator_logic.core.seeding import _resolve_world_seed, _mix_seed
from generator_logic.core.warp import apply_domain_warp

F32 = np.float32

# ------------------ FBM ядро (уникально для мультифрактала) ------------------
@njit(cache=True, fastmath=True)
def _fbm_unit(u, v, octaves, gain, seed):
    amp = F32(1.0)
    freq = F32(1.0)
    total = F32(0.0)
    norm = F32(0.0)
    for i in range(octaves):
        n = value_noise_2d(u * freq, v * freq, seed + i) * F32(2.0) - F32(1.0)
        total += amp * n
        norm  += amp
        amp   *= F32(gain)
        freq  *= F32(2.0)
    return F32(0.0) if norm < F32(1e-6) else total / norm

# ------------------ Основное ядро мультифрактала ------------------
@njit(cache=True, fastmath=True, parallel=True)
def _generate_fractal_kernel(
    out_array,
    u_norm, v_norm, # нормированные координаты
    seed_main,
    is_ridged, is_billowy,
    octaves, roughness
):
    H, W = out_array.shape
    for j in prange(H):
        for i in range(W):
            u = F32(u_norm[j, i])
            v = F32(v_norm[j, i])

            val = _fbm_unit(u, v, octaves, F32(roughness), seed_main)

            if is_ridged:
                result = F32(1.0) - np.abs(val)
            elif is_billowy:
                result = np.abs(val)
            else:
                result = val

            out_array[j, i] = result

# ------------------ Обёртка ------------------
def multifractal_wrapper(context: dict, fractal_params: dict, variation_params: dict, position_params: dict, warp_params: dict):
    # --- размеры/проект ---
    x = context['x_coords'].astype(np.float32, copy=False)  # метры
    z = context['z_coords'].astype(np.float32, copy=False)  # метры
    H, W = x.shape
    world_size_m = float(context.get('WORLD_SIZE_METERS', 5000.0))

    # --- сиды ---
    world_seed = _resolve_world_seed(context)
    # поддерживаем оба варианта: если передан seed, используем его; иначе берём seed_offset
    node_off = int(fractal_params.get('seed', fractal_params.get('seed_offset', 0)))
    seed_main  = _mix_seed(world_seed, node_off, 0)
    seed_warp  = _mix_seed(world_seed, node_off, 12345)

    # --- фрактальные параметры ---
    ntype = str(fractal_params.get('type', 'fbm') or 'fbm').lower()
    octaves = max(1, min(int(fractal_params.get('octaves', 8)), 32))
    roughness = float(fractal_params.get('roughness', 0.5))
    base_scale = max(float(fractal_params.get('scale', 0.5)), 1e-6)

    # --- позиционирование (в метрах) ---
    ox = float(position_params.get('offset_x', 0.0))
    oy = float(position_params.get('offset_y', 0.0))
    sx = float(position_params.get('scale_x', 1.0)) or 1.0
    sy = float(position_params.get('scale_y', 1.0)) or 1.0

    # world-space до варпа (метры):
    wx_raw = x * sx + ox
    wz_raw = z * sy + oy

    # --- warp (единый контракт) ---
    wt = (warp_params.get('type', 'none') or 'none').lower()
    wr_freq_1pm = float(warp_params.get('frequency', 0.0))
    wr_amp0_m   = float(warp_params.get('amp0_m', 0.0))
    wr_comp     = max(1, min(int(warp_params.get('complexity', 1)), 24))
    wr_rough    = float(warp_params.get('roughness', 0.5))
    wr_iters    = max(1, min(int(warp_params.get('iterations', 1)), 12))
    wr_attn     = float(warp_params.get('attenuation', 1.0))
    wr_aniso    = float(warp_params.get('anisotropy', 1.0))

    use_warp = (wt != 'none') and (wr_amp0_m > 0.0) and (wr_freq_1pm > 0.0)

    # --- применим варп в МЕТРАХ и сразу подготовим u,v ---
    denom = (world_size_m * base_scale + 1e-9)
    if use_warp:
        wx_warped = np.empty_like(wx_raw, dtype=np.float32)
        wz_warped = np.empty_like(wz_raw, dtype=np.float32)
        _apply_warp_to_grid(wx_warped, wz_warped, wx_raw.astype(np.float32), wz_raw.astype(np.float32),
                            wr_freq_1pm, wr_amp0_m, wr_comp, wr_rough, wr_iters, wr_attn, wr_aniso, seed_warp)
        u_norm = wx_warped / denom
        v_norm = wz_warped / denom
    else:
        u_norm = wx_raw / denom
        v_norm = wz_raw / denom

    # --- основное ядро ---
    out = np.empty((H, W), dtype=np.float32)
    _generate_fractal_kernel(
        out, u_norm, v_norm, seed_main,
        ntype.startswith('rid'), ntype.startswith('bil'),
        octaves, roughness
    )

    # --- постобработка (variation) ---
    f = out
    var = float(variation_params.get('variation', 1.0))
    smooth = float(variation_params.get('smoothness', 0.0))
    contrast = float(variation_params.get('contrast', 0.0))
    damping = float(variation_params.get('damping', 0.0))
    bias = float(variation_params.get('bias', 0.0))

    if damping > 0:
        u_low = (wx_raw / (denom * 2.0)).astype(np.float32)
        v_low = (wz_raw / (denom * 2.0)).astype(np.float32)
        low = np.empty_like(f)
        _generate_fractal_kernel(low, u_low, v_low, seed_main,
                                 ntype.startswith('rid'), ntype.startswith('bil'),
                                 max(octaves // 2, 1), roughness)
        f = normalize01(f, mode='minmax')
        low = normalize01(low, mode='minmax')
        f = (1.0 - damping) * f + damping * low

    f = normalize01(f, mode='minmax')

    if smooth != 0.0: f = np.power(f, 1.0 + smooth)
    if contrast != 0.0:
        m = float(np.mean(f))
        c = max(0.0, min(1.0, contrast)) * 2.0
        f = np.clip((f - m) * (1.0 + c) + m, 0.0, 1.0)
    if bias != 0.0:
        f = f + bias * 0.25
        f = normalize01(f, mode='minmax')
    if var != 1.0:
        m = float(np.mean(f))
        f = np.clip(m + (f - m) * var, 0.0, 1.0)

    return f.astype(np.float32)

# Вспомогательная сеточная обвязка для варпа
@njit(cache=True, fastmath=True, parallel=True)
def _apply_warp_to_grid(wx_out, wz_out, wx_in, wz_in,
                        wfreq_1pm, wamp0_m, wcomp, wrough, witers, wattn, waniso, seed):
    H, W = wx_in.shape
    for j in prange(H):
        for i in range(W):
            wx, wz = apply_domain_warp(
                wx_in[j, i], wz_in[j, i],
                F32(wfreq_1pm), F32(wamp0_m),
                wcomp, F32(wrough), witers, F32(wattn), F32(waniso),
                seed
            )
            wx_out[j, i] = wx
            wz_out[j, i] = wz
