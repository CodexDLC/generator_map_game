# editor/render_palettes.py
from __future__ import annotations
from typing import List, Tuple
import numpy as np
from vispy.color import Colormap

# Палитры: список контрольных точек (позиция 0..1, RGB 0..255)
PALETTES: dict[str, List[Tuple[float, Tuple[int, int, int]]]] = {
    "Rock": [
        (0.00, (30, 30, 34)),
        (0.35, (80, 80, 88)),
        (0.65, (150,150,160)),
        (0.90, (210,210,220)),
        (1.00, (235,240,250)),
    ],
    "Desert": [
        (0.00, (60, 38, 23)),
        (0.30, (120, 78, 38)),
        (0.60, (189,151, 79)),
        (0.85, (230,205,140)),
        (1.00, (250,240,210)),
    ],
    "Snow": [
        (0.00, (60, 60, 65)),
        (0.40, (120,120,130)),
        (0.75, (200,205,215)),
        (1.00, (245,250,255)),
    ],
    "Volcano": [
        (0.00, (20, 18, 18)),
        (0.40, (70, 55, 45)),
        (0.70, (120,95, 65)),
        (0.90, (170,150,120)),
        (1.00, (225,215,200)),
    ],
}

def make_colormap_from_palette(name: str) -> Colormap:
    """Colormap для SurfacePlot(cmap=...), без per-vertex цветов."""
    stops = PALETTES.get(name) or PALETTES["Rock"]
    pos = [p for p, _ in stops]
    rgb = [[c/255.0 for c in col] for _, col in stops]
    return Colormap(rgb, controls=pos)

def map_palette_cpu(z01: np.ndarray, name: str) -> np.ndarray:
    """
    Перевод нормализованных высот z∈[0,1] в RGB (H,W,3) на CPU.
    Линейная интерполяция по контрольным точкам палитры.
    """
    stops = PALETTES.get(name) or PALETTES["Rock"]
    xs = np.array([p for p,_ in stops], dtype=np.float32)
    cols = np.array([[r,g,b] for _,(r,g,b) in stops], dtype=np.float32) / 255.0

    z = np.clip(z01, 0.0, 1.0).astype(np.float32, copy=False)
    # Для каждого пикселя ищем соседние контрольные точки
    idx = np.searchsorted(xs, z, side="right")
    idx0 = np.clip(idx-1, 0, len(xs)-1)
    idx1 = np.clip(idx,   0, len(xs)-1)
    x0 = xs[idx0]; x1 = xs[idx1]
    c0 = cols[idx0]; c1 = cols[idx1]
    # избегаем деления на ноль
    denom = np.maximum(x1 - x0, 1e-6)
    t = (z - x0) / denom
    rgb = c0 * (1.0 - t)[..., None] + c1 * t[..., None]
    return np.clip(rgb, 0.0, 1.0)
