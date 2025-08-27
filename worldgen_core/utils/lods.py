# worldgen_core/utils/lods.py
from __future__ import annotations
from pathlib import Path
import math
import numpy as np
import imageio.v2 as imageio

from worldgen_core.io.io_png import save_png16

def stitch_height(base: Path, width: int, height: int, chunk: int) -> np.ndarray:
    """
    Сшивает height.png из chunk_{x}_{y}/height.png -> общий HxW (uint16).
    """
    base = Path(base)
    canvas = np.zeros((height, width), dtype=np.uint16)
    ny, nx = math.ceil(height / chunk), math.ceil(width / chunk)
    for j in range(ny):
        for i in range(nx):
            p = base / f"chunk_{i}_{j}" / "height.png"
            if not p.exists():
                continue
            tile = imageio.imread(p.as_posix()).astype(np.uint16)
            h, w = tile.shape[:2]
            y0, x0 = j * chunk, i * chunk
            canvas[y0:y0 + h, x0:x0 + w] = tile
    return canvas

def export_lods_from_chunks(base: Path, width: int, height: int, chunk: int, factors: list[int]) -> None:
    """
    Генерирует lower-LOD тайлы из исходных chunk_{x}_{y}/height.png.
    Пишет в подкаталоги: base/height_lod{factor}/chunk_{x}_{y}.png
    """
    base = Path(base)
    ny, nx = math.ceil(height / chunk), math.ceil(width / chunk)

    for factor in sorted({f for f in factors if isinstance(f, int) and f >= 2}):
        outdir = base / f"height_lod{factor}"
        outdir.mkdir(exist_ok=True)
        for j in range(ny):
            for i in range(nx):
                src = base / f"chunk_{i}_{j}" / "height.png"
                if not src.exists():
                    continue
                tile = imageio.imread(src.as_posix()).astype(np.uint16)
                # простейший даунсемплинг без интерполяции (детерминированный и быстрый)
                ds = tile[::factor, ::factor]
                save_png16(outdir / f"chunk_{i}_{j}.png", ds)
