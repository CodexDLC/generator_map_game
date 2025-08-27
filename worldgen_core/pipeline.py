# worldgen_core/pipeline.py
from pathlib import Path
import math
import numpy as np

from setting.config import GenConfig
from worldgen_core.biome import biome_block, biome_palette
from worldgen_core.edges import apply_edge_falloff, to_uint16
from worldgen_core.utils.core import (
    build_full_height_f32, normalize_heightmap, edge_params, slice_block,
    export_chunk_height_png, export_chunk_biome_png, append_canvases,
    export_for_godot, write_metadata
)

def generate_world(cfg: GenConfig, update_queue=None):
    base = Path(cfg.out_dir) / cfg.world_id / cfg.version
    base.mkdir(parents=True, exist_ok=True)

    cols = math.ceil(cfg.width / cfg.chunk)
    rows = math.ceil(cfg.height / cfg.chunk)

    full = build_full_height_f32(cfg)
    full = normalize_heightmap(full)
    ocean_norm, falloff_px = edge_params(cfg)

    canvas_h = np.zeros((cfg.height, cfg.width), dtype=np.uint16) if cfg.export_for_godot else None
    canvas_b = np.zeros((cfg.height, cfg.width), dtype=np.uint8)  if (cfg.export_for_godot and cfg.with_biomes) else None

    for cy in range(rows):
        for cx in range(cols):
            block, x0, y0, w, h = slice_block(full, cfg, cx, cy)
            block = apply_edge_falloff(block, cx, cy, cols, rows, width_px=falloff_px, ocean=ocean_norm, power=1.8)

            u16 = to_uint16(block)
            chunk_dir = base / f"chunk_{cx}_{cy}"
            export_chunk_height_png(chunk_dir, u16)

            b = None
            if cfg.with_biomes:
                b = biome_block(block, cfg.seed, x0, y0,
                                land_height_m=cfg.land_height_m,
                                meters_per_pixel=cfg.meters_per_pixel,
                                biome_config=cfg.biome_config)
                export_chunk_biome_png(chunk_dir, b)
                if update_queue is not None:
                    pal = biome_palette()
                    update_queue.put((cx, cy, pal[b]))

            append_canvases(canvas_h, canvas_b, u16, b, x0, y0, w, h)

    if cfg.export_for_godot:
        export_for_godot(base / "godot_export_full", canvas_h, canvas_b)

    if update_queue is not None:
        update_queue.put(("done", None, None))

    write_metadata(base, cfg)
