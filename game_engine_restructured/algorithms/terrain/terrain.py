# ==============================================================================
# Файл: game_engine_restructured/algorithms/terrain/terrain.py
# Назначение: Генерация геометрии ландшафта (карты высот).
# ВЕРСЯ 16.0: Интегрирован патч от пользователя:
#              - Ширина каньонов задается в метрах через градиент v_noise.
#              - Добавлен слой микрорельефа ("strata") на крутые склоны.
#              - Проведена чистка и оптимизация.
# ==============================================================================

from __future__ import annotations
from typing import Any, Dict
import math
import numpy as np
from scipy.ndimage import gaussian_filter

from .slope import _apply_slope_limiter, compute_slope_mask
from ...core.noise.fast_noise import fbm_amplitude, voronoi_grid, fbm_grid_warped


# ==============================================================================
# --- БЛОК 1: Вспомогательные утилиты ---
# ==============================================================================

def _apply_shaping_curve(grid: np.ndarray, power: float) -> None:
    if power != 1.0: np.power(grid, power, out=grid)


def _print_range(tag: str, arr: np.ndarray) -> None:
    mn, mx = float(np.min(arr)), float(np.max(arr))
    print(f"[DIAGNOSTIC] {tag}: min={mn:.3f} max={mx:.3f} range={mx - mn:.3f}")


def _vectorized_smoothstep(x: np.ndarray, edge0: np.ndarray | float, edge1: np.ndarray | float) -> np.ndarray:
    dtype = x.dtype
    span = edge1 - edge0
    t = np.divide(x - edge0, span, out=np.zeros_like(x, dtype=dtype), where=span != 0)
    t = np.clip(t, dtype.type(0.0), dtype.type(1.0))
    return t * t * (dtype.type(3.0) - dtype.type(2.0) * t)


# ==============================================================================
# --- БЛОК 2: Универсальная функция генерации слоя ---
# ==============================================================================

def _generate_layer(
        seed: int, layer_cfg: Dict, base_coords_x: np.ndarray, base_coords_z: np.ndarray,
        cell_size: float, scratch_buffer: np.ndarray,
) -> np.ndarray:
    # (Эта функция остается без изменений, так как она универсальна)
    amp = float(layer_cfg.get("amp_m", 0.0))
    if amp <= 0: return np.zeros_like(base_coords_x)

    orientation = math.radians(float(layer_cfg.get("orientation_deg", 0.0)))
    aspect = float(layer_cfg.get("aspect", 1.0))
    cr, sr = math.cos(orientation), math.sin(orientation)

    warp_cfg = layer_cfg.get("warp", {});
    warp_strength = float(warp_cfg.get("strength_m", 0.0))
    coords_x, coords_z = np.copy(base_coords_x), np.copy(base_coords_z)
    if warp_strength > 0:
        warp_scale = float(warp_cfg.get("scale_tiles", 1000)) * cell_size
        warp_freq = 1.0 / warp_scale if warp_scale > 0 else 0.0
        norm2 = fbm_amplitude(0.5, 2)
        warp_u_noise = fbm_grid_warped(seed ^ 0x1234, coords_x * warp_freq, coords_z * warp_freq, 1.0, 2) / max(norm2,
                                                                                                                1e-6)
        warp_v_noise = fbm_grid_warped(seed ^ 0x5678, coords_x * warp_freq, coords_z * warp_freq, 1.0, 2) / max(norm2,
                                                                                                                1e-6)
        warp_u_scaled = warp_u_noise * warp_strength * aspect;
        warp_v_scaled = warp_v_noise * warp_strength
        warp_x = warp_u_scaled * cr - warp_v_scaled * sr;
        warp_z = warp_u_scaled * sr + warp_v_scaled * cr
        coords_x += warp_x;
        coords_z += warp_z

    scale_parallel = float(layer_cfg.get("scale_tiles_parallel", layer_cfg.get("scale_tiles", 1000))) * cell_size
    scale_perp = scale_parallel / aspect if aspect > 0 else scale_parallel
    final_coords_x = (coords_x * cr - coords_z * sr) / max(scale_parallel, 1e-9)
    final_coords_z = (coords_x * sr + coords_z * cr) / max(scale_perp, 1e-9)

    octaves = int(layer_cfg.get("octaves", 3));
    is_ridge = bool(layer_cfg.get("ridge", False))
    noise = fbm_grid_warped(seed=seed, coords_x=final_coords_x, coords_z=final_coords_z, freq0=1.0, octaves=octaves,
                            ridge=is_ridge)

    is_base = bool(layer_cfg.get("is_base", False));
    is_positive = bool(layer_cfg.get("positive_only", False))
    norm_factor = max(fbm_amplitude(0.5, octaves), 1e-6)
    if is_base:
        noise = (noise / norm_factor + 1.0) * 0.5 if not is_ridge else noise / norm_factor
        np.clip(noise, 0.0, 1.0, out=noise)
    else:
        noise = np.clip(noise / norm_factor, -1.0, 1.0)
        if is_positive: noise = (noise + 1.0) * 0.5

    smoothing_sigma = float(layer_cfg.get("smoothing_sigma_post_shape", 0.0))
    if smoothing_sigma > 0:
        gaussian_filter(noise, sigma=smoothing_sigma, output=scratch_buffer, mode="reflect")
        noise = scratch_buffer.copy()

    return noise * amp


# ==============================================================================
# --- БЛОК 3: Главная функция-оркестратор (pipeline) ---
# ==============================================================================

def generate_elevation_region(
        seed: int, scx: int, scz: int, region_size_chunks: int, chunk_size: int, preset: Any, scratch_buffers: dict,
) -> np.ndarray:
    cfg = getattr(preset, "elevation", {});
    spectral_cfg = cfg.get("spectral", {}) or {}
    ext_size = (region_size_chunks + 2) * chunk_size;
    cell_size = float(getattr(preset, "cell_size", 1.0))
    base_wx = (scx * region_size_chunks - 1) * chunk_size;
    base_wz = (scz * region_size_chunks - 1) * chunk_size
    z_coords_base, x_coords_base = np.mgrid[0:ext_size, 0:ext_size]
    x_coords_base = (x_coords_base.astype(np.float32) + base_wx) * cell_size
    z_coords_base = (z_coords_base.astype(np.float32) + base_wz) * cell_size
    height_grid = np.zeros((ext_size, ext_size), dtype=np.float32)

    # --- ЭТАП 1: Создание основного рельефа ---
    if "continents" in spectral_cfg:
        height_grid += _generate_layer(seed, {**spectral_cfg["continents"], "is_base": True}, x_coords_base,
                                       z_coords_base, cell_size, scratch_buffers["a"])
    if "large_features" in spectral_cfg:
        height_grid += _generate_layer(seed + 1, spectral_cfg["large_features"], x_coords_base, z_coords_base,
                                       cell_size, scratch_buffers["a"])

    # --- ЭТАП 2: Вырезание асимметричных каньонов ---
    canyons_cfg = spectral_cfg.get("canyons", {})
    side_mask = None
    if canyons_cfg.get("enabled", False):
        print("  -> Carving asymmetric canyons (meter-based width)...")
        scale = float(canyons_cfg.get("scale_tiles", 1000)) * cell_size
        v_noise = voronoi_grid(seed ^ 0xDEADBEEF, x_coords_base, z_coords_base, 1.0 / scale if scale > 0 else 0).astype(
            np.float32, copy=False)

        # --- НОВАЯ ЛОГИКА: Ширина в метрах через градиент ---
        gx = np.gradient(v_noise, cell_size, axis=1);
        gz = np.gradient(v_noise, cell_size, axis=0)
        grad = np.sqrt(gx * gx + gz * gz) + 1e-6

        min_width_m = float(canyons_cfg.get("min_width_m", 1.0))
        width_soft_m = float(canyons_cfg.get("width_soft_m", 8.0));
        width_hard_m = float(canyons_cfg.get("width_hard_m", 2.0))

        soft_side_eps = float(canyons_cfg.get("soft_side_eps", 0.02))
        side_mask = _vectorized_smoothstep(v_noise, 0.5 - soft_side_eps, 0.5 + soft_side_eps)

        width_m_map = np.maximum(width_hard_m * (1.0 - side_mask) + width_soft_m * side_mask, min_width_m)
        w = width_m_map * grad

        _print_range("v_noise", v_noise);
        _print_range("side_mask", side_mask);
        _print_range("width_m_map (meters)", width_m_map);

        total_depth = float(canyons_cfg.get("depth_m", 30.0));
        steps = int(canyons_cfg.get("terracing_steps", 4))
        soft_factor = float(canyons_cfg.get("terracing_softness_factor", 1.5));
        depth_per_step = total_depth / steps if steps > 0 else 0
        eps = np.float32(1e-6)
        for i in range(steps):
            w_step = (1 + i * soft_factor) * w
            t0 = np.clip(0.5 - 0.5 * w_step, 0.0, 1.0)
            t1 = np.clip(0.5 + 0.5 * w_step, 0.0, 1.0)
            t1 = np.maximum(t1, t0 + eps)
            height_grid -= (1.0 - _vectorized_smoothstep(v_noise, t0, t1)) * depth_per_step

    # --- ЭТАП 3: Микрорельеф скал и сглаживание ---
    strata_cfg = spectral_cfg.get("strata_cliffs", {})
    if strata_cfg.get("enabled", False):
        print("  -> Adding strata micro-relief to cliffs...")
        cliff_mask = compute_slope_mask(height_grid, cell_size, float(strata_cfg.get("slope_angle_deg", 40.0)),
                                        2).astype(np.float32)
        strata_noise = _generate_layer(seed + 777, strata_cfg, x_coords_base, z_coords_base, cell_size,
                                       scratch_buffers["a"])
        height_grid += strata_noise * cliff_mask

    limiter_cfg = cfg.get("slope_limiter", {});
    post_limiter_cfg = canyons_cfg.get("post_limiter", {})
    if limiter_cfg.get("enabled", False):
        _apply_slope_limiter(height_grid, math.tan(math.radians(limiter_cfg.get("max_angle_deg", 50.0))), cell_size,
                             int(limiter_cfg.get("iterations", 32)))
    if canyons_cfg.get("enabled", False) and post_limiter_cfg.get("enabled", True):
        _apply_slope_limiter(height_grid, math.tan(math.radians(post_limiter_cfg.get("max_angle_deg", 55.0))),
                             cell_size, int(post_limiter_cfg.get("iterations", 24)))

    if "erosion" in spectral_cfg:
        height_grid += _generate_layer(seed + 2, spectral_cfg["erosion"], x_coords_base, z_coords_base, cell_size,
                                       scratch_buffers["a"])

    # --- ЭТАП 4: Финальные сдвиг/клип ---
    height_grid += float(cfg.get("base_height_m", 0.0))
    np.clip(height_grid, 0.0, float(cfg.get("max_height_m", 80.0)), out=height_grid)
    _print_range("height_final", height_grid)
    return height_grid.copy()