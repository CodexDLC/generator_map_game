import json, math
from pathlib import Path
import numpy as np
from .config import GenConfig
from .noise import height_block
from .edges import apply_edge_boost_radial, to_uint16
from .biome import biome_block, biome_palette
from .io_png import save_png16, save_biome_png, load_png16

def _meta_path(base: Path) -> Path: return base / "metadata.json"

def _write_meta(base: Path, cfg: GenConfig):
    meta = {
        "world_id": cfg.world_id,
        "version": cfg.version,  # <- строковая версия
        "seed": cfg.seed,
        "width": cfg.width, "height": cfg.height, "chunk_size": cfg.chunk,
        "encoding": {"height": "uint16_0..65535"},
        "noise": {"scale": cfg.scale, "octaves": cfg.octaves,
                  "lacunarity": cfg.lacunarity, "gain": cfg.gain},
        "ocean_level": cfg.ocean_level, "edge_boost": cfg.edge_boost,
        "edge_margin_frac": cfg.edge_margin_frac,
        "origin_px": {"x": cfg.origin_x, "y": cfg.origin_y},
        "meters_per_pixel": cfg.meters_per_pixel, "height_range_m": cfg.height_range_m,
        "layers": ["height"] + (["biome"] if cfg.with_biomes else [])
    }
    base.mkdir(parents=True, exist_ok=True)
    _meta_path(base).write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

def generate_world(cfg: GenConfig, on_progress=None):
    base = Path(cfg.out_dir) / cfg.world_id / cfg.version   # <- версия в пути
    hdir, bdir = base / "height", base / "biome"
    _write_meta(base, cfg)
    x_chunks = math.ceil(cfg.width / cfg.chunk)
    y_chunks = math.ceil(cfg.height / cfg.chunk)
    total = x_chunks * y_chunks; k = 0

    for y0 in range(0, cfg.height, cfg.chunk):
        for x0 in range(0, cfg.width, cfg.chunk):
            w = min(cfg.chunk, cfg.width  - x0)
            h = min(cfg.chunk, cfg.height - y0)
            gx0, gy0 = cfg.origin_x + x0, cfg.origin_y + y0

            block = height_block(cfg.seed, gx0, gy0, w, h,
                                 cfg.scale, cfg.octaves, cfg.lacunarity, cfg.gain)
            block = apply_edge_boost_radial(
                block, gx0, gy0, w, h,
                cfg.width + cfg.origin_x, cfg.height + cfg.origin_y,
                cfg.edge_boost, cfg.edge_margin_frac
            )
            save_png16(hdir / f"chunk_{x0//cfg.chunk}_{y0//cfg.chunk}.png", to_uint16(block))

            if cfg.with_biomes:
                b = biome_block(block, cfg.seed, gx0, gy0, ocean_level=cfg.ocean_level)
                save_biome_png(bdir / f"chunk_{x0//cfg.chunk}_{y0//cfg.chunk}.png", b, biome_palette())

            if on_progress:
                on_progress(k, total, x0//cfg.chunk, y0//cfg.chunk)
            k += 1

def extract_window(src_base: Path,  # .../<world>/vX
                   dst_base: Path,  # .../<new_world>/vY
                   origin_x: int, origin_y: int, width: int, height: int,
                   chunk: int, copy_biomes: bool = True):
    meta = json.loads(_meta_path(src_base).read_text(encoding="utf-8"))
    src_chunk = int(meta["chunk_size"])
    has_biome = "biome" in meta.get("layers", [])
    height_dir = src_base / "height"; biome_dir = src_base / "biome"

    cx0 = origin_x // src_chunk; cy0 = origin_y // src_chunk
    cx1 = (origin_x + width  - 1) // src_chunk
    cy1 = (origin_y + height - 1) // src_chunk

    canvas_h = np.zeros((height, width), dtype=np.uint16)
    canvas_b = np.zeros((height, width), dtype=np.uint8) if (copy_biomes and has_biome) else None

    for cy in range(cy0, cy1 + 1):
        for cx in range(cx0, cx1 + 1):
            src = height_dir / f"chunk_{cx}_{cy}.png"
            if not src.exists(): continue
            tile = load_png16(src)
            x_start = cx * src_chunk; y_start = cy * src_chunk

            ix0 = max(origin_x, x_start); iy0 = max(origin_y, y_start)
            ix1 = min(origin_x + width, x_start + tile.shape[1])
            iy1 = min(origin_y + height, y_start + tile.shape[0])
            if ix1 <= ix0 or iy1 <= iy0: continue

            sx0, sy0 = ix0 - x_start, iy0 - y_start
            dx0, dy0 = ix0 - origin_x, iy0 - origin_y
            h, w = iy1 - iy0, ix1 - ix0

            canvas_h[dy0:dy0+h, dx0:dx0+w] = tile[sy0:sy0+h, sx0:sx0+w]

            if canvas_b is not None:
                import imageio.v2 as imageio
                bsrc = biome_dir / f"chunk_{cx}_{cy}.png"
                if bsrc.exists():
                    brgb = imageio.imread(bsrc.as_posix())
                    pal = biome_palette()
                    flat = brgb.reshape(-1, 3).astype(np.int16)
                    d = ((flat[:,None,:]-pal[None,:,:])**2).sum(-1)
                    idx = d.argmin(1).reshape(brgb.shape[0], brgb.shape[1]).astype(np.uint8)
                    canvas_b[dy0:dy0+h, dx0:dx0+w] = idx[sy0:sy0+h, sx0:sx0+w]

    dst_base.mkdir(parents=True, exist_ok=True)
    (dst_base / "height").mkdir(exist_ok=True)
    if canvas_b is not None: (dst_base / "biome").mkdir(exist_ok=True)

    nx = math.ceil(width / chunk); ny = math.ceil(height / chunk)
    for j in range(ny):
        for i in range(nx):
            x0 = i * chunk; y0 = j * chunk
            save_png16(dst_base / "height" / f"chunk_{i}_{j}.png",
                       canvas_h[y0:y0+chunk, x0:x0+chunk])
            if canvas_b is not None:
                import imageio.v2 as imageio
                pal = biome_palette()
                rgb = pal[canvas_b[y0:y0+chunk, x0:x0+chunk]]
                imageio.imwrite((dst_base / "biome" / f"chunk_{i}_{j}.png").as_posix(), rgb)

    new_meta = {
        "world_id": dst_base.parent.name,
        "version": dst_base.name,      # <- берём из имени папки
        "seed": meta.get("seed", -1),
        "width": width, "height": height, "chunk_size": chunk,
        "encoding": {"height": "uint16_0..65535"},
        "layers": ["height"] + (["biome"] if canvas_b is not None else [])
    }
    _meta_path(dst_base).write_text(json.dumps(new_meta, ensure_ascii=False, indent=2), encoding="utf-8")
