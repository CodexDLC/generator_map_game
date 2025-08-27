# worldgen_core/utils/core.py
from __future__ import annotations
from pathlib import Path
import math, os, multiprocessing
import numpy as np

from setting.config import GenConfig
from setting.constants import BIOME_ID_WATER_VISUAL, BIOME_ID_BEACH
from worldgen_core.noise import height_block
from worldgen_core.edges import to_uint16, apply_edge_falloff
from worldgen_core.biome import biome_block, biome_palette
from worldgen_core.io.io_png import (
    save_png16, save_biome_png, load_png16, save_raw16, save_control_map_exr_rf, save_temperature_png
)

# ---------- Control Map (Terrain3D FORMAT_RF) ----------
def build_control_uint32(biome_ids_u8: np.ndarray, mapping: dict[int,int] | None = None) -> np.ndarray:
    if mapping:
        base_id = np.zeros_like(biome_ids_u8, dtype=np.uint32)
        for b, t in mapping.items():
            base_id[biome_ids_u8 == b] = np.uint32(t & 31)
    else:
        base_id = (biome_ids_u8.astype(np.uint32) & 31)

    overlay  = np.zeros_like(base_id, dtype=np.uint32)
    blend    = np.zeros_like(base_id, dtype=np.uint32)  # 0 = только base
    uv_angle = np.zeros_like(base_id, dtype=np.uint32)
    uv_scale = np.zeros_like(base_id, dtype=np.uint32)
    hole     = np.zeros_like(base_id, dtype=np.uint32)
    nav      = np.ones_like (base_id, dtype=np.uint32)
    auto     = np.zeros_like(base_id, dtype=np.uint32)  # manual

    ctrl = ((base_id & 0x1F) << 27) \
         | ((overlay & 0x1F) << 22) \
         | ((blend   & 0xFF) << 14) \
         | ((uv_angle & 0x0F) << 10) \
         | ((uv_scale & 0x07) << 7)  \
         | ((hole    & 0x01) << 2)   \
         | ((nav     & 0x01) << 1)   \
         |  (auto    & 0x01)
    return ctrl

# ---------- Сборка полной height-карты ----------
def _generate_chunk_task(args):
    cfg, cx, cy = args
    x0, y0 = cx * cfg.chunk, cy * cfg.chunk
    w = min(cfg.chunk, cfg.width  - x0)
    h = min(cfg.chunk, cfg.height - y0)
    gx0, gy0 = cfg.origin_x + x0, cfg.origin_y + y0
    block = height_block(
        cfg.seed, gx0, gy0, w, h,
        cfg.plains_scale, cfg.plains_octaves,
        cfg.mountains_scale, cfg.mountains_octaves,
        cfg.mask_scale,
        cfg.mountain_strength,
        cfg.height_distribution_power,
        cfg.lacunarity, cfg.gain
    )
    return (cx, cy, block)

def build_full_height_f32(cfg: GenConfig) -> np.ndarray:
    cols = math.ceil(cfg.width / cfg.chunk)
    rows = math.ceil(cfg.height / cfg.chunk)
    tasks = [(cfg, cx, cy) for cy in range(rows) for cx in range(cols)]

    H = np.zeros((cfg.height, cfg.width), dtype=np.float32)
    with multiprocessing.Pool(processes=max(1, os.cpu_count() - 2)) as pool:
        for cx, cy, block in pool.map(_generate_chunk_task, tasks):
            x0, y0 = cx * cfg.chunk, cy * cfg.chunk
            h, w = block.shape
            H[y0:y0+h, x0:x0+w] = block
    return H

def normalize_heightmap(H: np.ndarray) -> np.ndarray:
    mn, mx = float(H.min()), float(H.max())
    return (H - mn) / (mx - mn) if mx > mn else H

def edge_params(cfg: GenConfig) -> tuple[float, int]:
    ocean_norm = float(np.clip(cfg.biome_config.ocean_level_m / max(cfg.land_height_m, 1e-6), 0.0, 1.0))
    falloff_px = max(16, int(0.06 * min(cfg.width, cfg.height)))
    return ocean_norm, falloff_px

def slice_block(full: np.ndarray, cfg: GenConfig, cx: int, cy: int) -> tuple[np.ndarray, int, int, int, int]:
    x0, y0 = cx * cfg.chunk, cy * cfg.chunk
    w = min(cfg.chunk, cfg.width  - x0)
    h = min(cfg.chunk, cfg.height - y0)
    return full[y0:y0+h, x0:x0+w], x0, y0, w, h

# ---------- Экспорт и аккумуляция ----------
def export_chunk_height_png(chunk_dir: Path, block_u16: np.ndarray) -> None:
    chunk_dir.mkdir(parents=True, exist_ok=True)
    save_png16(chunk_dir / "height.png", block_u16)

def export_chunk_biome_png(chunk_dir: Path, b: np.ndarray) -> None:
    pal = biome_palette()
    save_biome_png(chunk_dir / "biome.png", b, pal)

def append_canvases(canvas_h: np.ndarray | None, canvas_b: np.ndarray | None,
                    block_u16: np.ndarray, b: np.ndarray | None,
                    x0: int, y0: int, w: int, h: int) -> None:
    if canvas_h is not None:
        canvas_h[y0:y0+h, x0:x0+w] = block_u16
    if canvas_b is not None and b is not None:
        canvas_b[y0:y0+h, x0:x0+w] = b

def export_for_godot(godot_dir: Path, canvas_h: np.ndarray | None, canvas_b: np.ndarray | None) -> None:
    godot_dir.mkdir(exist_ok=True)
    if canvas_h is not None:
        save_raw16(godot_dir / "heightmap.r16", canvas_h)
    if canvas_b is not None:
        save_biome_png(godot_dir / "biomemap.png", canvas_b, biome_palette())
        b = canvas_b.copy()
        b[b == BIOME_ID_WATER_VISUAL] = BIOME_ID_BEACH
        ctrl = build_control_uint32(b)
        save_control_map_exr_rf(godot_dir / "controlmap.exr", ctrl)

def write_metadata(base: Path, cfg: GenConfig) -> None:
    import json
    meta = {
        "world_id": cfg.world_id,
        "version": cfg.version,
        "seed": cfg.seed,
        "width": cfg.width, "height": cfg.height, "chunk_size": cfg.chunk,
        "encoding": {"height": "uint16_0..65535"},
        "noise": {
            "plains_scale": cfg.plains_scale, "plains_octaves": cfg.plains_octaves,
            "mountains_scale": cfg.mountains_scale, "mountains_octaves": cfg.mountains_octaves,
            "mask_scale": cfg.mask_scale,
            "mountain_strength": cfg.mountain_strength,
            "height_distribution_power": cfg.height_distribution_power,
            "lacunarity": cfg.lacunarity, "gain": cfg.gain
        },
        "ocean_level": cfg.biome_config.ocean_level_m,
        "origin_px": {"x": cfg.origin_x, "y": cfg.origin_y},
        "meters_per_pixel": cfg.meters_per_pixel,
        "land_height_m": cfg.land_height_m,
        "layers": ["height"] + (["biome"] if cfg.with_biomes else [])
    }
    base.mkdir(parents=True, exist_ok=True)
    (base / "metadata.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

def compute_temperature(full_h_norm: np.ndarray, cfg) -> np.ndarray:
    """
    Температура T(x,y), °C: широтный градиент + охлаждение с высотой + крупномасштабный шум.
    full_h_norm — нормализованная высота [0..1] той же размерности, что карта.
    Параметры читаем из cfg.* с дефолтами, чтобы не ломать существующий конфиг.
    """
    H_m = full_h_norm.astype(np.float32) * float(getattr(cfg, "land_height_m", 1000.0))

    # Параметры климата
    T_eq   = float(getattr(cfg, "temp_equator_C",        24.0))
    T_pole = float(getattr(cfg, "temp_pole_C",           -6.0))
    axis   = float(getattr(cfg, "temp_axis_deg",          0.0))  # 0° = "север вверх"
    lapse  = float(getattr(cfg, "temp_lapse_C_per_km",    6.5))  # °C/км
    n_scale= float(getattr(cfg, "temp_noise_scale_m",  12000.0)) # м
    n_amp  = float(getattr(cfg, "temp_noise_amp_C",       4.0))

    h, w = full_h_norm.shape
    # широтный градиент
    ang = np.deg2rad(axis)
    gx, gy = np.cos(ang), np.sin(ang)
    xs = np.arange(w, dtype=np.float32)
    ys = np.arange(h, dtype=np.float32)
    X, Y = np.meshgrid(xs, ys)
    u = X * gx + Y * gy
    u -= u.min()
    umax = u.max()
    if umax > 1e-6:
        u /= umax
    # тёплый "экватор" ↔ холодный "полюс"
    T_lat = T_pole + (T_eq - T_pole) * (1.0 - u)

    # охлаждение с высотой
    T = T_lat - lapse * (H_m / 1000.0)

    # крупный шум климата (без гор/маски — только "равнинный" канал)
    # используем имеющийся height_block как источник сглаженного шума
    # seed смещаем, метры→пиксели через meters_per_pixel
    mpp = float(getattr(cfg, "meters_per_pixel", 1.0))
    scale_px = max(1.0, n_scale / max(mpp, 1e-6))
    N = height_block(
        int(getattr(cfg, "seed", 0)) ^ 0xA1B2C3D4,
        0, 0, w, h,
        scale_px, 3,  # plains_scale, plains_octaves
        0.0, 0,  # mountains_scale, mountains_octaves (выкл)
        0.0,  # mask_scale
        0.0,  # mountain_strength
        1.0,  # height_distribution_power
        2.0, 0.5  # lacunarity, gain
    ).astype(np.float32)

    T += n_amp * (N - 0.5) * 2.0
    return T.astype(np.float32)


def export_chunk_temperature_png(chunk_dir: Path, temp_chunk_C: np.ndarray,
                                 tmin: float = -30.0, tmax: float = 40.0) -> None:
    chunk_dir.mkdir(parents=True, exist_ok=True)
    save_temperature_png(chunk_dir / "temp.png", temp_chunk_C, tmin=tmin, tmax=tmax)




def apply_volcano_island(full_norm: np.ndarray, cfg) -> np.ndarray:
    """
    Вулканический остров БЕЗ кратера:
      - крутой пик в центре (R_peak)
      - мягкое широкое "плечо" / равнины (R_shoulder)
      - затем спад к океану к радиусу острова (R_island, band)
    Ничего не опускает ниже базового рельефа: только добавляет высоту.
    """
    H, W = full_norm.shape
    mpp = float(getattr(cfg, "meters_per_pixel", 1.0))

    cxcy = getattr(cfg, "volcano_center_px", None)
    cx, cy = (W // 2, H // 2) if not cxcy else (int(cxcy[0]), int(cxcy[1]))

    # параметры из конфигурации
    peak_add_m   = float(getattr(cfg, "peak_add_m", 180.0))       # добавка высоты в пике (м)
    R_peak_m     = float(getattr(cfg, "volcano_radius_m", 2500.0))  # радиус крутого конуса
    R_shoulder_m = float(getattr(cfg, "shoulder_radius_m", 5500.0)) # радиус "плеча" / равнины
    R_island_m   = float(getattr(cfg, "island_radius_m", 9000.0))   # край острова (начало спада к воде)
    band_m       = float(getattr(cfg, "island_band_m", 2000.0))     # ширина спада
    ridge_amp    = float(getattr(cfg, "ridge_noise_amp", 0.08))     # легкая рябь по окружности
    land_h_m     = float(getattr(cfg, "land_height_m", 150.0))

    # сетка расстояний
    xs = np.arange(W, dtype=np.float32)
    ys = np.arange(H, dtype=np.float32)
    X, Y = np.meshgrid(xs, ys)
    r_m = np.hypot((X - cx) * mpp, (Y - cy) * mpp)

    # профиль: сумма двух радиальных "шляп"
    # 1) крутой центральный конус
    p1 = 2.6
    s1 = 1.0 - np.power(np.clip(r_m / max(R_peak_m, 1e-6), 0.0, 1.0), p1)
    s1 = np.clip(s1, 0.0, 1.0)

    # 2) широкое "плечо" (пологий склон/равнина)
    p2 = 1.2
    s2 = 1.0 - np.power(np.clip(r_m / max(R_shoulder_m, 1e-6), 0.0, 1.0), p2)
    s2 = np.clip(s2, 0.0, 1.0)

    # смешиваем: центр — за счет s1, средние расстояния — за счет s2
    profile = 0.75 * s1 + 0.35 * s2
    profile = np.clip(profile, 0.0, 1.0)

    # легкая рябь по углу (чтобы не было идеального круга)
    if ridge_amp > 0.0:
        angle = np.arctan2(Y - cy, X - cx)
        ridges = 0.5 + 0.5 * np.sin(6.0 * angle)
        profile = np.clip(profile * (1.0 + ridge_amp * (ridges - 0.5)), 0.0, 1.0)

    # перевод в нормализованную добавку
    peak_add_norm = np.clip(peak_add_m / max(land_h_m, 1e-6), 0.0, 1.0)
    delta = profile * peak_add_norm

    out = np.clip(full_norm + delta, 0.0, 1.0)

    # внешний спад к океану (smoothstep)
    t = np.clip((r_m - R_island_m) / max(band_m, 1e-6), 0.0, 1.0)
    t = t * t * (3.0 - 2.0 * t)  # smoothstep
    out = np.clip(out * (1.0 - t), 0.0, 1.0)

    return out.astype(np.float32)