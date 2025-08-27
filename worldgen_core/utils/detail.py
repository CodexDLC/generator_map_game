# worldgen_core/utils/detail.py
from __future__ import annotations
from pathlib import Path
import math
import numpy as np
from PIL import Image

from setting.config import GenConfig
from worldgen_core.noise import height_block
from worldgen_core.io.io_png import load_png16, save_png16, save_raw16


def detail_heightmap(base_h16: np.ndarray, upscale: int, seed: int, gx0: int, gy0: int,
                     detail_scale: float, detail_strength: float,
                     octaves: int = 6, lacunarity: float = 2.0, gain: float = 0.5,
                     new_w: int | None = None, new_h: int | None = None) -> np.ndarray:
    """
    Апскейл карты высот + добавление процедурной «детали».
    Возвращает uint16.
    """
    if upscale <= 1 and detail_strength <= 0:
        return base_h16

    if new_w is None:
        new_w = base_h16.shape[1] * max(upscale, 1)
    if new_h is None:
        new_h = base_h16.shape[0] * max(upscale, 1)

    # upscale bicubic -> float32 [0..1]
    up = Image.fromarray(base_h16).resize((new_w, new_h), Image.Resampling.BICUBIC)
    up_f32 = np.asarray(up, dtype=np.float32) / 65535.0

    if detail_strength > 0:
        dn = height_block(
            seed, gx0 * max(upscale, 1), gy0 * max(upscale, 1), new_w, new_h,
            detail_scale, octaves, 0.0, 0.0, 0.0,   # используем один источник шума
            lacunarity, gain
        )
        out_f32 = up_f32 * (1.0 - detail_strength) + dn * detail_strength
    else:
        out_f32 = up_f32

    # квантуем обратно
    out_f32 = np.clip(out_f32, 0.0, 1.0)
    return (out_f32 * 65535.0 + 0.5).astype(np.uint16)


def detail_world_chunk(world_path: Path, out_dir: Path, cx: int, cy: int,
                       upscale: int, detail_scale: float, detail_strength: float,
                       seed_override: int | None = None) -> str:
    """
    Детализирует один чанк: читает height.png, апскейлит и добавляет шум.
    Пишет PNG и R16. Возвращает путь к папке результатов.
    """
    meta_path = Path(world_path) / "metadata.json"
    meta = {} if not meta_path.exists() else __import__("json").loads(meta_path.read_text(encoding="utf-8"))

    chunk_size = int(meta.get("chunk_size", 512))
    src = Path(world_path) / f"chunk_{cx}_{cy}" / "height.png"
    if not src.is_file():
        raise FileNotFoundError(f"Нет файла: {src}")

    base_h16 = load_png16(src)
    w, h = base_h16.shape[1], base_h16.shape[0]
    new_w, new_h = w * max(upscale, 1), h * max(upscale, 1)

    seed = int(meta.get("seed", 0))
    if seed_override is not None:
        seed = int(seed_override)

    gx0, gy0 = cx * chunk_size, cy * chunk_size
    detailed = detail_heightmap(
        base_h16, upscale, seed ^ 0xDEADBEEF, gx0, gy0,
        detail_scale, detail_strength, octaves=6, lacunarity=2.0, gain=0.5,
        new_w=new_w, new_h=new_h
    )

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    save_png16(out_dir / f"detailed_chunk_{cx}_{cy}.png", detailed)
    save_raw16(out_dir / f"detailed_chunk_{cx}_{cy}.r16", detailed)
    return str(out_dir.resolve())


def detail_entire_world(world_path: Path, out_dir: Path, upscale: int, detail_scale: float, detail_strength: float,
                        on_progress=None) -> str:
    """
    Детализирует все чанки мира. Вызывает detail_world_chunk по сетке чанков.
    """
    meta_path = Path(world_path) / "metadata.json"
    meta = {} if not meta_path.exists() else __import__("json").loads(meta_path.read_text(encoding="utf-8"))

    width  = int(meta.get("width", 0))
    height = int(meta.get("height", 0))
    chunk  = int(meta.get("chunk_size", 512))

    cols = math.ceil(width / chunk) if chunk > 0 else 0
    rows = math.ceil(height / chunk) if chunk > 0 else 0
    total = cols * rows
    k = 0

    for cy in range(rows):
        for cx in range(cols):
            if on_progress:
                on_progress(k, total, f"Детализация чанка {cx},{cy}...")
            detail_world_chunk(world_path, out_dir, cx, cy, upscale, detail_scale, detail_strength)
            k += 1

    if on_progress:
        on_progress(total, total, "Готово!")
    return str(Path(out_dir).resolve())
