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
    save_png16, save_biome_png, load_png16, save_raw16, save_control_map_exr_rf
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
