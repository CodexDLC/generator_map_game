import json
import math
from pathlib import Path

import imageio.v2 as imageio
import numpy as np

from setting.config import GenConfig
from worldgen_core.noise import height_block
from worldgen_core.edges import apply_edge_boost_radial, to_uint16, apply_edge_falloff
from worldgen_core.biome import biome_block, biome_palette
from worldgen_core.io.io_png import save_png16, save_biome_png, load_png16, save_raw16, save_control_map_r32
from worldgen_core.utils.overview import _build_overview
from worldgen_core.utils.nav import _build_navgrid

try:
    import cv2
except ImportError:
    cv2 = None


def _meta_path(base: Path) -> Path: return base / "metadata.json"


def _write_meta(base: Path, cfg: GenConfig):
    meta = {
        "world_id": cfg.world_id,
        "version": cfg.version,
        "seed": cfg.seed,
        "width": cfg.width, "height": cfg.height, "chunk_size": cfg.chunk,
        "encoding": {"height": "uint16_0..65535"},
        "noise": {"scale": cfg.scale, "octaves": cfg.octaves,
                  "lacunarity": cfg.lacunarity, "gain": cfg.gain},
        "ocean_level": cfg.ocean_level,
        "edge_boost": cfg.edge_boost,
        "edge_margin_frac": cfg.edge_margin_frac,
        "origin_px": {"x": cfg.origin_x, "y": cfg.origin_y},
        "meters_per_pixel": cfg.meters_per_pixel,
        "land_height_m": cfg.land_height_m,
        "layers": ["height"] + (["biome"] if cfg.with_biomes else [])
    }
    base.mkdir(parents=True, exist_ok=True)
    _meta_path(base).write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")


def generate_world(cfg: GenConfig, update_queue=None):
    base = Path(cfg.out_dir) / cfg.world_id / cfg.version
    _write_meta(base, cfg)

    canvas_h = np.zeros((cfg.height, cfg.width), dtype=np.uint16) if cfg.export_for_godot else None
    canvas_b = np.zeros((cfg.height, cfg.width), dtype=np.uint8) if cfg.export_for_godot and cfg.with_biomes else None

    cols = math.ceil(cfg.width / cfg.chunk)
    rows = math.ceil(cfg.height / cfg.chunk)

    for cy in range(rows):
        for cx in range(cols):
            x0 = cx * cfg.chunk
            y0 = cy * cfg.chunk
            w = min(cfg.chunk, cfg.width - x0)
            h = min(cfg.chunk, cfg.height - y0)
            gx0, gy0 = cfg.origin_x + x0, cfg.origin_y + y0

            chunk_dir = base / f"chunk_{cx}_{cy}"
            chunk_dir.mkdir(parents=True, exist_ok=True)

            block_f32 = height_block(cfg.seed, gx0, gy0, w, h, cfg.scale, cfg.octaves, cfg.lacunarity, cfg.gain)
            block_f32 = apply_edge_boost_radial(block_f32, gx0, gy0, w, h, cfg.width + cfg.origin_x,
                                                cfg.height + cfg.origin_y, cfg.edge_boost, cfg.edge_margin_frac)

            if cfg.flat_edges:
                block_f32 = apply_edge_falloff(block_f32, cx, cy, cols, rows)

            block_u16 = to_uint16(block_f32)
            save_png16(chunk_dir / "height.png", block_u16)

            if canvas_h is not None:
                canvas_h[y0:y0 + h, x0:x0 + w] = block_u16

            if cfg.with_biomes:
                b = biome_block(block_f32, cfg.seed, gx0, gy0, ocean_level=cfg.ocean_level,
                                land_height_m=cfg.land_height_m, meters_per_pixel=cfg.meters_per_pixel,
                                biome_config=cfg.biome_config)
                palette = biome_palette()
                save_biome_png(chunk_dir / "biome.png", b, palette)
                if canvas_b is not None:
                    canvas_b[y0:y0 + h, x0:x0 + w] = b

                if update_queue is not None:
                    rgb_preview = palette[b]
                    update_queue.put((cx, cy, rgb_preview))

            if cfg.export_for_godot:
                save_raw16(chunk_dir / "heightmap.r16", block_u16)
                if cfg.with_biomes:
                    save_control_map_r32(chunk_dir / "controlmap.r32", b)

    if cfg.export_for_godot:
        godot_dir = base / "godot_export_full"
        godot_dir.mkdir(exist_ok=True)
        save_raw16(godot_dir / "heightmap.r16", canvas_h)
        if canvas_b is not None:
            save_control_map_r32(godot_dir / "controlmap.r32", canvas_b)
            palette = biome_palette()
            save_biome_png(godot_dir / "biomemap.png", canvas_b, palette)

    if update_queue is not None:
        update_queue.put(("done", None, None))


def extract_window(src_base: Path, dst_base: Path, origin_x: int, origin_y: int, width: int, height: int,
                   chunk: int, copy_biomes: bool = True):
    meta = json.loads(_meta_path(src_base).read_text(encoding="utf-8"))
    src_chunk = int(meta["chunk_size"])
    has_biome = "biome" in meta.get("layers", [])

    cx0, cy0 = origin_x // src_chunk, origin_y // src_chunk
    cx1, cy1 = (origin_x + width - 1) // src_chunk, (origin_y + height - 1) // src_chunk

    canvas_h = np.zeros((height, width), dtype=np.uint16)
    canvas_b = np.zeros((height, width), dtype=np.uint8) if (copy_biomes and has_biome) else None

    for cy in range(cy0, cy1 + 1):
        for cx in range(cx0, cx1 + 1):
            src_chunk_dir = src_base / f"chunk_{cx}_{cy}"
            src_height_path = src_chunk_dir / "height.png"
            if not src_height_path.exists(): continue
            tile = load_png16(src_height_path)
            x_start, y_start = cx * src_chunk, cy * src_chunk

            ix0, iy0 = max(origin_x, x_start), max(origin_y, y_start)
            ix1, iy1 = min(origin_x + width, x_start + tile.shape[1]), min(origin_y + height, y_start + tile.shape[0])
            if ix1 <= ix0 or iy1 <= iy0: continue

            sx0, sy0 = ix0 - x_start, iy0 - y_start
            dx0, dy0 = ix0 - origin_x, iy0 - origin_x
            h, w = iy1 - iy0, ix1 - ix0

            canvas_h[dy0:dy0 + h, dx0:dx0 + w] = tile[sy0:sy0 + h, sx0:sx0 + w]

            if canvas_b is not None:
                src_biome_path = src_chunk_dir / "biome.png"
                if src_biome_path.exists():
                    brgb = imageio.imread(src_biome_path.as_posix())
                    pal = biome_palette()
                    flat = brgb.reshape(-1, 3).astype(np.int16)
                    d = ((flat[:, None, :] - pal[None, :, :]) ** 2).sum(-1)
                    idx = d.argmin(1).reshape(brgb.shape[0], brgb.shape[1]).astype(np.uint8)
                    canvas_b[dy0:dy0 + h, dx0:dx0 + w] = idx[sy0:sy0 + h, sx0:sx0 + w]

    dst_base.mkdir(parents=True, exist_ok=True)

    nx, ny = math.ceil(width / chunk), math.ceil(height / chunk)
    for j in range(ny):
        for i in range(nx):
            x0, y0 = i * chunk, j * chunk
            dst_chunk_dir = dst_base / f"chunk_{i}_{j}"
            dst_chunk_dir.mkdir(exist_ok=True)
            save_png16(dst_chunk_dir / "height.png", canvas_h[y0:y0 + chunk, x0:x0 + chunk])
            if canvas_b is not None:
                pal = biome_palette()
                rgb = pal[canvas_b[y0:y0 + chunk, x0:x0 + chunk]]
                imageio.imwrite((dst_chunk_dir / "biome.png").as_posix(), rgb)

    new_meta = {
        "world_id": dst_base.parent.name, "version": dst_base.name, "seed": meta.get("seed", -1),
        "width": width, "height": height, "chunk_size": chunk,
        "encoding": {"height": "uint16_0..65535"},
        "layers": ["height"] + (["biome"] if canvas_b is not None else [])
    }
    _meta_path(dst_base).write_text(json.dumps(new_meta, ensure_ascii=False, indent=2), encoding="utf-8")


def _stitch_height(base: Path, width: int, height: int, chunk: int) -> np.ndarray:
    """Собрать весь мир в uint16 из сохранённых чанков."""
    canvas = np.zeros((height, width), dtype=np.uint16)
    ny, nx = math.ceil(height / chunk), math.ceil(width / chunk)
    for j in range(ny):
        for i in range(nx):
            p = base / f"chunk_{i}_{j}" / "height.png"
            if not p.exists(): continue
            tile = imageio.imread(p.as_posix())
            h, w = tile.shape[0], tile.shape[1]
            y0, x0 = j * chunk, i * chunk
            canvas[y0:y0 + h, x0:x0 + w] = tile
    return canvas


def _export_lods(base: Path, cfg: GenConfig):
    """Экспортирует чанки с уменьшенным разрешением (LODs)."""
    hdir = base / "height"
    ny, nx = math.ceil(cfg.height / cfg.chunk), math.ceil(cfg.width / cfg.chunk)
    for factor in sorted({k for k in cfg.lods if isinstance(k, int) and k >= 2}):
        outdir = base / f"height_lod{factor}"
        outdir.mkdir(exist_ok=True)
        for j in range(ny):
            for i in range(nx):
                p = hdir / f"chunk_{i}_{j}.png"
                if not p.exists(): continue
                tile = imageio.imread(p.as_posix()).astype(np.uint16)
                tile_downsampled = tile[::factor, ::factor]
                imageio.imwrite((outdir / f"chunk_{i}_{j}.png").as_posix(), tile_downsampled)


def _build_navgrid(base: Path, cfg: GenConfig):
    """Очень простой navgrid: блокируем по уклону и воде."""
    H16 = _stitch_height(base, cfg.width, cfg.height, cfg.chunk)

    total_height_range = cfg.land_height_m / max(1.0 - cfg.ocean_level, 1e-6)
    Hm = (H16.astype(np.float32) / 65535.0) * total_height_range

    gy, gx = np.gradient(Hm, cfg.meters_per_pixel, cfg.meters_per_pixel)
    slope = np.degrees(np.arctan(np.hypot(gx, gy)))
    blocked = slope > cfg.navgrid_max_slope_deg
    if cfg.navgrid_block_water:
        water_h_abs = cfg.ocean_level * total_height_range
        blocked |= (Hm <= water_h_abs + 1e-3)

    cell = max(1, int(round(cfg.navgrid_cell_m / cfg.meters_per_pixel)))
    h2, w2 = (Hm.shape[0] // cell) * cell, (Hm.shape[1] // cell) * cell
    B = blocked[:h2, :w2].reshape(h2 // cell, cell, w2 // cell, cell).any(axis=(1, 3)).astype(np.uint8)

    ndir = base / "navgrid"
    ndir.mkdir(exist_ok=True)
    np.save((ndir / f"grid_cell{cfg.navgrid_cell_m:.2f}m.npy").as_posix(), B)
    prev = (B * 255).astype(np.uint8)
    imageio.imwrite((ndir / f"grid_cell{cfg.navgrid_cell_m:.2f}m_preview.png").as_posix(), prev)
    (ndir / "meta.json").write_text(json.dumps({
        "cell_m": cfg.navgrid_cell_m,
        "max_slope_deg": cfg.navgrid_max_slope_deg,
        "block_water": cfg.navgrid_block_water
    }, ensure_ascii=False, indent=2), encoding="utf-8")


def _detail_heightmap(base_h16: np.ndarray, upscale: int, seed: int, gx0: int, gy0: int,
                      detail_scale: float, detail_strength: float, octaves: int, lac: float, gain: float, new_w=None,
                      new_h=None) -> np.ndarray:
    if upscale <= 1 and detail_strength <= 0:
        return base_h16

    from PIL import Image
    base_img = Image.fromarray(base_h16)
    upscaled_img = base_img.resize((new_w, new_h), Image.Resampling.BICUBIC)
    upscaled_h_f32 = np.array(upscaled_img, dtype=np.float32) / 65535.0

    if detail_strength > 0:
        detail_noise_f32 = height_block(seed, gx0 * upscale, gy0 * upscale, new_w, new_h,
                                        detail_scale, octaves, lac, gain)
        final_h_f32 = (upscaled_h_f32 * (1.0 - detail_strength)) + (detail_noise_f32 * detail_strength)
    else:
        final_h_f32 = upscaled_h_f32

    return to_uint16(final_h_f32)


def detail_world_chunk(world_path: Path, out_dir: Path, cx: int, cy: int,
                       upscale: int, detail_scale: float, detail_strength: float):
    meta_path = world_path / "metadata.json"
    with open(meta_path, 'r', encoding='utf-8') as f:
        meta = json.load(f)

    chunk_path = world_path / f"chunk_{cx}_{cy}" / "height.png"
    if not chunk_path.is_file():
        raise FileNotFoundError(f"Исходный чанк не найден: {chunk_path}")

    base_h16 = load_png16(chunk_path)
    chunk_size = meta['chunk_size']
    gx0, gy0 = cx * chunk_size, cy * chunk_size

    detailed_h16 = _detail_heightmap(
        base_h16, upscale, meta['seed'] ^ 0xDEADBEEF,
        gx0, gy0, detail_scale, detail_strength,
        octaves=6, lac=2.0, gain=0.5
    )

    out_dir.mkdir(parents=True, exist_ok=True)
    out_path_png = out_dir / f"detailed_chunk_{cx}_{cy}.png"
    out_path_r16 = out_dir / f"detailed_chunk_{cx}_{cy}.r16"

    save_png16(out_path_png, detailed_h16)
    save_raw16(out_path_r16, detailed_h16)
    return str(out_path_png.parent.resolve())


def detail_entire_world(world_path: Path, out_dir: Path, upscale: int, detail_scale: float,
                        detail_strength: float, on_progress=None):
    meta_path = world_path / "metadata.json"
    with open(meta_path, 'r', encoding='utf-8') as f:
        meta = json.load(f)

    cols = math.ceil(meta['width'] / meta['chunk_size'])
    rows = math.ceil(meta['height'] / meta['chunk_size'])
    total = cols * rows
    k = 0

    for r in range(rows):
        for c in range(cols):
            if on_progress:
                on_progress(k, total, f"Детализация чанка {c},{r}...")

            detail_world_chunk(world_path, out_dir, c, r, upscale, detail_scale, detail_strength)
            k += 1

    if on_progress:
        on_progress(total, total, "Готово!")

    return str(out_dir.resolve())