# Файл: game_engine_restructured/algorithms/climate/climate.py
from __future__ import annotations
from typing import TYPE_CHECKING, Dict, Any
import numpy as np
from math import radians, cos, sin
from scipy.ndimage import distance_transform_edt, gaussian_filter, binary_erosion
from numba import njit

from ...core.preset.model import Preset
from ...core.types import GenResult
from ...core import constants as const

if TYPE_CHECKING:
    from ...core.preset.model import Preset


# ---------- НАЧАЛО: ВАШ NUMBA-СОВМЕСТИМЫЙ ШУМ (ПАТЧ №2) ----------
@njit(inline='always', cache=True)
def _u32(x: int) -> int:
    return x & 0xFFFFFFFF


@njit(inline='always', cache=True)
def _hash2(ix: int, iz: int, seed: int) -> int:
    x = _u32(ix) ^ _u32(seed * 0x9E3779B1)
    y = _u32(iz) ^ _u32(seed * 0x85EBCA77)
    h = _u32(x * 0x85EBCA6B) ^ _u32(y * 0xC2B2AE35)
    h ^= h >> 16
    h = _u32(h * 0x7FEB352D)
    h ^= h >> 15
    h = _u32(h * 0x846CA68B)
    h ^= h >> 16
    return h


@njit(inline='always', cache=True)
def _rand01(ix: int, iz: int, seed: int) -> float:
    return (_hash2(ix, iz, seed) / 4294967296.0)


@njit(inline='always', cache=True)
def _fade(t: float) -> float:
    # 6t^5 - 15t^4 + 10t^3 (quintic)
    return t * t * t * (t * (t * 6.0 - 15.0) + 10.0)


@njit(inline='always', cache=True)
def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


@njit(inline='always', cache=True)
def _value_noise_2d(x: float, z: float, seed: int) -> float:
    xi = int(np.floor(x));
    xf = x - xi
    zi = int(np.floor(z));
    zf = z - zi
    u = _fade(xf);
    v = _fade(zf)

    n00 = _rand01(xi + 0, zi + 0, seed)
    n10 = _rand01(xi + 1, zi + 0, seed)
    n01 = _rand01(xi + 0, zi + 1, seed)
    n11 = _rand01(xi + 1, zi + 1, seed)

    nx0 = _lerp(n00, n10, u)
    nx1 = _lerp(n01, n11, u)
    return _lerp(nx0, nx1, v)


@njit(cache=True)
def _fbm_grid(seed: int, x0_px: int, z0_px: int, size: int,
              mpp: float, freq0: float, octaves: int = 3,
              lacunarity: float = 2.0, gain: float = 0.5) -> np.ndarray:
    """
    fBm на сетке size×size. freq0 — в 1/м (т.е. частота в мировых метрах).
    """
    g = np.zeros((size, size), dtype=np.float32)
    for o in range(octaves):
        amp = gain ** o
        freq = freq0 * (lacunarity ** o)
        for j in range(size):
            wz = (z0_px + j) * mpp * freq
            for i in range(size):
                wx = (x0_px + i) * mpp * freq
                # приводим из 0..1 к -1..1:
                g[j, i] += amp * (2.0 * _value_noise_2d(wx, wz, seed + o * 131) - 1.0)
    return g


# ---------- КОНЕЦ ВАШЕГО ПАТЧА ----------


def apply_climate_to_surface(chunk: GenResult):
    # Эта функция остается без изменений
    if "temperature" not in chunk.layers or "humidity" not in chunk.layers:
        return

    size = chunk.size
    temp_grid = chunk.layers["temperature"]
    humidity_grid = chunk.layers["humidity"]
    surface_grid = chunk.layers["surface"]
    overlay_grid = chunk.layers["overlay"]
    overlay_snow_id = const.SURFACE_KIND_TO_ID.get(const.KIND_OVERLAY_SNOW, 0)

    for z in range(size):
        for x in range(size):
            if surface_grid[z][x] != const.KIND_BASE_DIRT:
                continue
            temp = temp_grid[z][x]
            humidity = humidity_grid[z][x]

            if temp < 2:
                surface_grid[z][x] = const.KIND_BASE_GRASS
            elif temp > 22 and humidity < 0.25:
                surface_grid[z][x] = const.KIND_BASE_CRACKED
            elif humidity > 0.5:
                surface_grid[z][x] = const.KIND_BASE_DIRT
            else:
                surface_grid[z][x] = const.KIND_BASE_GRASS
            if temp < 0:
                overlay_grid[z][x] = overlay_snow_id
    print(f"  -> Climate applied to surface for chunk ({chunk.cx}, {chunk.cz}).")


def generate_climate_maps(
        stitched_layers: Dict[str, np.ndarray],
        preset: Preset,
        region_seed: int,
        base_cx: int,
        base_cz: int,
        region_pixel_size: int,
        region_size: int
):
    climate_cfg = preset.climate
    if not climate_cfg.get("enabled"):
        return

    mpp = float(getattr(preset, "cell_size", 0.5))
    size = region_pixel_size

    # --- 1. Генерация температуры с вашим патчем ---
    temp_cfg = climate_cfg.get("temperature", {})
    if temp_cfg.get("enabled"):
        base_temp = temp_cfg.get("base_c", 18.0)
        noise_amp = temp_cfg.get("noise_amp_c", 6.0)
        lapse_rate = temp_cfg.get("lapse_rate_c_per_m", -0.0065)
        clamp_min, clamp_max = temp_cfg.get("clamp_c", [-15.0, 35.0])

        y_coords = np.arange(base_cz * preset.size, (base_cz + region_size) * preset.size, dtype=np.float32)
        latitude_grad = y_coords * temp_cfg.get("gradient_c_per_km", -0.02) * -0.1
        temperature_grid = np.full((size, size), base_temp, dtype=np.float32)
        temperature_grid += latitude_grad[:, np.newaxis]

        noise_scale_m = float(temp_cfg.get("noise_scale_tiles", 9000.0)) * mpp
        freq0 = 0.0 if noise_scale_m <= 0 else 1.0 / noise_scale_m

        fbm = _fbm_grid(int(region_seed), base_cx * preset.size, base_cz * preset.size,
                        size, mpp, freq0, octaves=3)

        temperature_grid += fbm * noise_amp
        temperature_grid += stitched_layers['height'] * lapse_rate
        np.clip(temperature_grid, clamp_min, clamp_max, out=temperature_grid)
        stitched_layers["temperature"] = temperature_grid

    # --- 2. Генерация влажности с вашим патчем ---
    humidity_cfg = climate_cfg.get("humidity", {})
    if humidity_cfg.get("enabled"):
        base_humidity = humidity_cfg.get("base", 0.45)
        clamp_min, clamp_max = humidity_cfg.get("clamp", [0.0, 1.0])

        is_water = (stitched_layers["navigation"] == const.NAV_WATER)
        water_core = binary_erosion(is_water, iterations=3)
        water_edge = is_water & ~binary_erosion(is_water, iterations=1)

        dist_water_m = distance_transform_edt(~water_core) * mpp
        dist_edge_m = distance_transform_edt(~water_edge) * mpp

        L_coast_m = float(humidity_cfg.get("L_coast_m", 250.0))
        L_river_m = float(humidity_cfg.get("L_river_m", 30.0))
        coast_term = np.exp(-dist_water_m / max(L_coast_m, 1e-6))
        river_term = np.exp(-dist_edge_m / max(L_river_m, 1e-6))
        coast_term = gaussian_filter(coast_term, sigma=2.0)

        H = stitched_layers["height"]
        Hs = gaussian_filter(H, sigma=1.0)
        gx, gz = np.gradient(Hs, mpp)

        wind_dir = float(humidity_cfg.get("wind_dir_deg", 225.0))
        wdx = cos(radians(wind_dir))
        wdz = -sin(radians(wind_dir))
        lift = gaussian_filter(np.maximum(0.0, gx * wdx + gz * wdz), sigma=2.0)
        shadow = gaussian_filter(np.maximum(0.0, -(gx * wdx + gz * wdz)), sigma=2.0)

        T = stitched_layers.get("temperature",
                                np.full((size, size), humidity_cfg.get("temp_fallback_c", 18.0), dtype=np.float32))
        T0, Tspan = float(humidity_cfg.get("dry_T0_c", 24.0)), float(humidity_cfg.get("dry_span_c", 12.0))
        temp_dry = np.clip((T - T0) / max(Tspan, 1e-6), 0.0, 1.0)

        noise_scale_m = float(humidity_cfg.get("noise_scale_tiles", 10000.0)) * mpp
        freq0 = 0.0 if noise_scale_m <= 0 else 1.0 / noise_scale_m

        fbm = _fbm_grid(int(region_seed ^ 0x5A5A5A5A),
                        base_cx * preset.size, base_cz * preset.size,
                        size, mpp, freq0, octaves=3)
        if (fbm.max() - fbm.min()) > 1e-6:
            fbm = (fbm - fbm.min()) / (fbm.max() - fbm.min())
        fbm = fbm - 0.5

        w_coast = float(humidity_cfg.get("w_coast", 0.35))
        w_river = float(humidity_cfg.get("w_river", 0.15))
        w_orog = float(humidity_cfg.get("w_orography", 0.30))
        w_shadow = float(humidity_cfg.get("w_rain_shadow", 0.25))
        w_noise = float(humidity_cfg.get("w_noise", 0.15))
        w_dry = float(humidity_cfg.get("w_temp_dry", 0.20))

        humidity = (base_humidity
                    + w_coast * coast_term
                    + w_river * river_term
                    + w_orog * lift
                    - w_shadow * shadow
                    + w_noise * fbm
                    - w_dry * temp_dry)

        np.clip(humidity, clamp_min, clamp_max, out=humidity)
        stitched_layers["humidity"] = humidity.astype(np.float32)

    print(f"  -> Climate maps generated for region.")