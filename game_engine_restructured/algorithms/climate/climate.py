# Файл: game_engine_restructured/algorithms/climate/climate.py
from __future__ import annotations
from typing import TYPE_CHECKING, Dict, Any, Tuple
import numpy as np
import math
from math import radians, cos, sin
from scipy.ndimage import distance_transform_edt, gaussian_filter, binary_erosion
from numba import njit

from ...core.preset.model import Preset
from ...core.types import GenResult
from ...core import constants as const

if TYPE_CHECKING:
    from ...core.preset.model import Preset


# ---------- НАЧАЛО: ВАШИ УТИЛИТЫ ДЛЯ БЕСШОВНОЙ ОБРАБОТКИ ----------

def _stats(name: str, arr: np.ndarray):
    """Выводит отладочную статистику для массива."""
    print(f"[STAT] {name:>12} min={arr.min():7.3f} max={arr.max():7.3f} mean={arr.mean():7.3f}")

def _derive_seed(base: int, tag: str) -> int:
    """Детерминированно порождает новый seed из базового и строки-тега."""
    h = 2166136261
    for b in tag.encode('utf-8'):
        h ^= b
        h = (h * 16777619) & 0xFFFFFFFF
    return (base ^ h) & 0xFFFFFFFF

def _fbm_amplitude(gain: float, octaves: int) -> float:
    """Вычисляет теоретическую максимальную амплитуду fBm для глобальной нормализации."""
    if gain == 1.0:
        return float(octaves)
    return (1.0 - gain**octaves) / (1.0 - gain)

def _pad_reflect(arr: np.ndarray, pad: int) -> np.ndarray:
    """Добавляет 'ореол' к массиву, отражая его края."""
    return np.pad(arr, pad_width=pad, mode='reflect')

def _edt_with_halo(mask: np.ndarray, pad: int, mpp: float) -> np.ndarray:
    """Выполняет Distance Transform с 'ореолом', чтобы избежать краевых артефактов."""
    pad_mask = _pad_reflect(mask, pad)
    d = distance_transform_edt(~pad_mask)
    return d[pad:-pad, pad:-pad] * mpp

def _gauss_with_halo(arr: np.ndarray, sigma: float, pad: int) -> np.ndarray:
    """Применяет фильтр Гаусса с 'ореолом'."""
    pad_arr = _pad_reflect(arr, pad)
    g = gaussian_filter(pad_arr, sigma=sigma)
    return g[pad:-pad, pad:-pad]

# ---------- КОНЕЦ УТИЛИТ ----------


# ---------- БЛОК NUMBA (С ИСПРАВЛЕННЫМ ЦИКЛОМ) ----------
@njit(inline='always', cache=True)
def _u32(x: int) -> int: return x & 0xFFFFFFFF

@njit(inline='always', cache=True)
def _hash2(ix: int, iz: int, seed: int) -> int:
    a = _u32(0x9e3779b1 + 2)  # любое “золотое” число ок
    b = a; c = a
    a = _u32(a + ix);  b = _u32(b + iz);  c = _u32(c + seed)

    a = _u32(a - b); a = _u32(a - c); a = _u32(a ^ (c >> 13))
    b = _u32(b - c); b = _u32(b - a); b = _u32(b ^ (a << 8))
    c = _u32(c - a); c = _u32(c - b); c = _u32(c ^ (b >> 13))

    a = _u32(a - b); a = _u32(a - c); a = _u32(a ^ (c >> 12))
    b = _u32(b - c); b = _u32(b - a); b = _u32(b ^ (a << 16))
    c = _u32(c - a); c = _u32(c - b); c = _u32(c ^ (b >> 5))

    a = _u32(a - b); a = _u32(a - c); a = _u32(a ^ (c >> 3))
    b = _u32(b - c); b = _u32(b - a); b = _u32(b ^ (a << 10))
    c = _u32(c - a); c = _u32(c - b); c = _u32(c ^ (b >> 15))

    return _u32(c)

@njit(inline='always', cache=True)
def _rand01(ix: int, iz: int, seed: int) -> float: return _hash2(ix, iz, seed) / 4294967296.0

@njit(inline='always', cache=True)
def _fade(t: float) -> float: return t*t*t*(t*(t*6.0-15.0)+10.0)

@njit(inline='always', cache=True)
def _lerp(a: float, b: float, t: float) -> float: return a + (b-a)*t

@njit(inline='always', cache=True)
def _value_noise_2d(x: float, z: float, seed: int) -> float:
    xi=int(np.floor(x)); xf=x-xi; zi=int(np.floor(z)); zf=z-zi
    u=_fade(xf); v=_fade(zf)
    n00=_rand01(xi,zi,seed); n10=_rand01(xi+1,zi,seed); n01=_rand01(xi,zi+1,seed); n11=_rand01(xi+1,zi+1,seed)
    nx0=_lerp(n00,n10,u); nx1=_lerp(n01,n11,u)
    return _lerp(nx0,nx1,v)

@njit(cache=True)
def _fbm_grid(seed: int, x0_px: int, z0_px: int, size: int, mpp: float, freq0: float,
              octaves: int, lacunarity: float, gain: float, rot_deg: float) -> np.ndarray:
    g = np.zeros((size, size), dtype=np.float32)
    cr = math.cos(math.radians(rot_deg)); sr = math.sin(math.radians(rot_deg))
    for o in range(octaves):
        amp = gain ** o
        freq = freq0 * (lacunarity ** o)
        for j in range(size):
            wz_m = (z0_px + j) * mpp
            # Ошибка 'i not defined' была здесь, теперь исправлено:
            for i in range(size):
                wx_m = (x0_px + i) * mpp
                rx = cr * wx_m - sr * wz_m; rz = sr * wx_m + cr * wz_m
                noise_val = _value_noise_2d(rx * freq, rz * freq, seed + o)
                g[j, i] += amp * (noise_val * 2.0 - 1.0)
    return g
# ---------------------------------------------------------------


def apply_climate_to_surface(chunk: GenResult):
    # Эта функция остается без изменений
    if "temperature" not in chunk.layers or "humidity" not in chunk.layers: return
    # ... (код функции без изменений) ...


def generate_climate_maps(
        stitched_layers: Dict[str, np.ndarray], preset: Preset, world_seed: int,
        base_cx: int, base_cz: int, region_pixel_size: int, region_size: int
):
    climate_cfg = preset.climate
    if not climate_cfg.get("enabled"): return

    mpp = float(getattr(preset, "cell_size", 0.5)); size = region_pixel_size
    HALO = 16

    # 1. Генерация температуры
    temp_cfg = climate_cfg.get("temperature", {})
    if temp_cfg.get("enabled"):
        base_temp=temp_cfg.get("base_c", 18.0); noise_amp=temp_cfg.get("noise_amp_c", 6.0)
        lapse_rate=temp_cfg.get("lapse_rate_c_per_m", -0.0065); clamp_min,clamp_max=temp_cfg.get("clamp_c", [-15.0, 35.0])
        y_coords=np.arange(base_cz*preset.size, (base_cz+region_size)*preset.size, dtype=np.float32)
        temperature_grid=np.full((size, size), base_temp, dtype=np.float32)
        temperature_grid += (y_coords*mpp*temp_cfg.get("gradient_c_per_km",-0.02)*0.001)[:, np.newaxis]

        scale_m_T = float(temp_cfg.get("noise_scale_tiles", 900.0)) * mpp
        freq0_T = 0.0 if scale_m_T <= 0 else (1.0 / scale_m_T) * 0.9973

        chunk_m = preset.size * mpp
        print(f"[DBG] Δ_T={chunk_m*freq0_T:.4f}")

        seed_T = _derive_seed(world_seed, "climate.temperature")
        fbm_T = _fbm_grid(seed_T, base_cx*preset.size, base_cz*preset.size, size, mpp, freq0_T,
                          octaves=5, lacunarity=2.07, gain=0.5, rot_deg=31.7)
        fbm_T /= _fbm_amplitude(0.5, 5)

        temperature_grid += fbm_T * noise_amp
        temperature_grid += stitched_layers['height'] * lapse_rate

        _stats("fbm_T", fbm_T); _stats("height", stitched_layers['height'])
        _stats("temp_preclip", temperature_grid)

        np.clip(temperature_grid, clamp_min, clamp_max, out=temperature_grid)
        stitched_layers["temperature"] = temperature_grid

    # 2. Генерация влажности
    humidity_cfg = climate_cfg.get("humidity", {})
    if humidity_cfg.get("enabled"):
        base_humidity=humidity_cfg.get("base", 0.45); clamp_min,clamp_max=humidity_cfg.get("clamp", [0.0, 1.0])
        is_water=(stitched_layers["navigation"]==const.NAV_WATER); water_core=binary_erosion(is_water,iterations=3)
        water_edge=is_water&~binary_erosion(is_water,iterations=1)

        dist_water_m=_edt_with_halo(water_core, HALO, mpp); dist_edge_m=_edt_with_halo(water_edge, HALO, mpp)
        L_coast_m=float(humidity_cfg.get("L_coast_m", 250.0)); L_river_m=float(humidity_cfg.get("L_river_m", 30.0))
        coast_term=gaussian_filter(np.exp(-dist_water_m/max(L_coast_m,1e-6)),sigma=2.0)
        river_term=np.exp(-dist_edge_m/max(L_river_m,1e-6))

        Hs=_gauss_with_halo(stitched_layers["height"],sigma=1.0,pad=HALO)
        gx,gz=np.gradient(Hs,mpp)
        ang=float(humidity_cfg.get("wind_dir_deg",225.0)); wdx,wdz=cos(radians(ang)),-sin(radians(ang))

        proj=gx*wdx+gz*wdz
        S0=float(humidity_cfg.get("orography_scale",0.25))
        lift=1.0-np.exp(-np.maximum(0.0,proj)/max(S0,1e-6))
        shadow=1.0-np.exp(-np.maximum(0.0,-proj)/max(S0,1e-6))
        lift=gaussian_filter(lift,sigma=2.0)
        shadow=gaussian_filter(shadow,sigma=2.0)

        T=stitched_layers.get("temperature",np.full((size,size),humidity_cfg.get("temp_fallback_c",18.0),dtype=np.float32))
        T0,Tspan=float(humidity_cfg.get("dry_T0_c",24.0)),float(humidity_cfg.get("dry_span_c",12.0))
        temp_dry=np.clip((T-T0)/max(Tspan,1e-6),0.0,1.0)

        scale_m_H = float(humidity_cfg.get("noise_scale_tiles", 1037.0)) * mpp
        freq0_H = 0.0 if scale_m_H <= 0 else (1.0 / scale_m_H) * 1.01127
        print(f"[DBG] Δ_H={chunk_m*freq0_H:.4f}")

        seed_H = _derive_seed(world_seed, "climate.humidity")
        fbm_H = _fbm_grid(seed_H, base_cx*preset.size, base_cz*preset.size, size, mpp, freq0_H,
                          octaves=5, lacunarity=2.11, gain=0.5, rot_deg=68.3)
        fbm_H /= _fbm_amplitude(0.5, 5)

        w_coast=float(humidity_cfg.get("w_coast",0.35)); w_river=float(humidity_cfg.get("w_river",0.15))
        w_orog=float(humidity_cfg.get("w_orography",0.30)); w_shadow=float(humidity_cfg.get("w_rain_shadow",0.25))
        w_noise=float(humidity_cfg.get("w_noise",0.15)); w_dry=float(humidity_cfg.get("w_temp_dry",0.20))

        humidity=(base_humidity+w_coast*coast_term+w_river*river_term+w_orog*lift-w_shadow*shadow+w_noise*fbm_H-w_dry*temp_dry)

        _stats("coast",coast_term); _stats("river",river_term); _stats("lift",lift); _stats("shadow",shadow)
        _stats("fbm_H",fbm_H); _stats("temp_dry",temp_dry); _stats("humid_preclip",humidity)

        np.clip(humidity,clamp_min,clamp_max,out=humidity)
        stitched_layers["humidity"]=humidity.astype(np.float32)

    print(f"  -> Climate maps generated for region.")