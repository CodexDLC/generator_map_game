# worldgen_core/utils/window.py
from __future__ import annotations
from pathlib import Path
import math
import numpy as np
import imageio.v2 as imageio

from worldgen_core.io.io_png import load_png16, save_png16
from worldgen_core.biome import biome_palette
from worldgen_core.io.io_png import save_biome_png

# ---------- чтение метаданных ----------
def read_meta(base: Path) -> dict:
    p = Path(base) / "metadata.json"
    return {} if not p.exists() else __import__("json").loads(p.read_text(encoding="utf-8"))

# ---------- утилиты чтения чанков ----------
def read_chunk_height(chunk_dir: Path) -> np.ndarray | None:
    p = Path(chunk_dir) / "height.png"
    return None if not p.exists() else load_png16(p)

def read_chunk_biome_indices(chunk_dir: Path) -> np.ndarray | None:
    """
    Возвращает карту индексов биомов из biome.png (по ближайшему цвету к палитре).
    """
    p = Path(chunk_dir) / "biome.png"
    if not p.exists():
        return None
    rgb = imageio.imread(p.as_posix())
    pal = biome_palette()
    flat = rgb.reshape(-1, 3).astype(np.int16)
    d = ((flat[:, None, :] - pal[None, :, :]) ** 2).sum(-1)
    idx = d.argmin(1).reshape(rgb.shape[0], rgb.shape[1]).astype(np.uint8)
    return idx

# ---------- извлечение окна ----------
def copy_window_canvases(src_base: Path, origin_x: int, origin_y: int, width: int, height: int,
                         copy_biomes: bool = True) -> tuple[np.ndarray, np.ndarray | None, int]:
    """
    Возвращает (canvas_h:uint16 HxW, canvas_b:uint8 HxW|None, src_chunk:int)
    """
    meta = read_meta(src_base)
    src_chunk = int(meta.get("chunk_size", 512))

    cx0, cy0 = origin_x // src_chunk, origin_y // src_chunk
    cx1, cy1 = (origin_x + width - 1) // src_chunk, (origin_y + height - 1) // src_chunk

    canvas_h = np.zeros((height, width), dtype=np.uint16)
    canvas_b = np.zeros((height, width), dtype=np.uint8) if (copy_biomes and "biome" in meta.get("layers", [])) else None

    for cy in range(cy0, cy1 + 1):
        for cx in range(cx0, cx1 + 1):
            cdir = Path(src_base) / f"chunk_{cx}_{cy}"
            h_tile = read_chunk_height(cdir)
            if h_tile is None:
                continue

            x_start, y_start = cx * src_chunk, cy * src_chunk
            ix0, iy0 = max(origin_x, x_start), max(origin_y, y_start)
            ix1, iy1 = min(origin_x + width, x_start + h_tile.shape[1]), min(origin_y + height, y_start + h_tile.shape[0])
            if ix1 <= ix0 or iy1 <= iy0:
                continue

            sx0, sy0 = ix0 - x_start, iy0 - y_start
            dx0, dy0 = ix0 - origin_x, iy0 - origin_y
            hh, ww = iy1 - iy0, ix1 - ix0

            canvas_h[dy0:dy0 + hh, dx0:dx0 + ww] = h_tile[sy0:sy0 + hh, sx0:sx0 + ww]

            if canvas_b is not None:
                b_idx = read_chunk_biome_indices(cdir)
                if b_idx is not None:
                    canvas_b[dy0:dy0 + hh, dx0:dx0 + ww] = b_idx[sy0:sy0 + hh, sx0:sx0 + ww]

    return canvas_h, canvas_b, src_chunk

# ---------- запись результата ----------
def write_window(dst_base: Path, canvas_h: np.ndarray, canvas_b: np.ndarray | None, chunk: int) -> None:
    """
    Разбивает канвасы по чанкам и сохраняет height.png / biome.png.
    """
    dst_base = Path(dst_base)
    dst_base.mkdir(parents=True, exist_ok=True)

    width, height = canvas_h.shape[1], canvas_h.shape[0]
    nx, ny = math.ceil(width / chunk), math.ceil(height / chunk)

    for j in range(ny):
        for i in range(nx):
            x0, y0 = i * chunk, j * chunk
            cdir = dst_base / f"chunk_{i}_{j}"
            cdir.mkdir(exist_ok=True)
            save_png16(cdir / "height.png", canvas_h[y0:y0 + chunk, x0:x0 + chunk])
            if canvas_b is not None:
                pal = biome_palette()
                rgb = pal[canvas_b[y0:y0 + chunk, x0:x0 + chunk]]
                save_biome_png(cdir / "biome.png", canvas_b[y0:y0 + chunk, x0:x0 + chunk], pal)

def write_window_metadata(dst_base: Path, world_id: str, version: str, seed: int,
                          width: int, height: int, chunk: int, has_biome: bool) -> None:
    meta = {
        "world_id": world_id,
        "version": version,
        "seed": seed,
        "width": width,
        "height": height,
        "chunk_size": chunk,
        "encoding": {"height": "uint16_0..65535"},
        "layers": ["height"] + (["biome"] if has_biome else []),
    }
    (Path(dst_base) / "metadata.json").write_text(
        __import__("json").dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )

# ---------- фасад ----------
def extract_window(src_base: Path, dst_base: Path, origin_x: int, origin_y: int,
                   width: int, height: int, chunk: int, copy_biomes: bool = True) -> None:
    meta = read_meta(src_base)
    canvas_h, canvas_b, _ = copy_window_canvases(src_base, origin_x, origin_y, width, height, copy_biomes)
    write_window(dst_base, canvas_h, canvas_b, chunk)
    write_window_metadata(
        dst_base,
        world_id=Path(dst_base).parent.name,
        version=Path(dst_base).name,
        seed=int(meta.get("seed", -1)),
        width=width, height=height, chunk=chunk,
        has_biome=(canvas_b is not None)
    )
