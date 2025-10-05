# editor/render_palettes.py
from __future__ import annotations
from typing import List, Tuple, Optional
import numpy as np
from vispy.color import Colormap

# Палитры: список контрольных точек (позиция 0..1, RGB 0..255)
PALETTES: dict[str, List[Tuple[float, Tuple[int, int, int]]]] = {
    "Rock": [
        (0.00, (40, 40, 44)),
        (0.35, (90, 90, 98)),
        (0.65, (160, 160, 170)),
        (0.90, (215, 215, 220)),
        (1.00, (245, 245, 250)),
    ],
    "Desert": [
        (0.00, (60, 38, 23)),
        (0.30, (120, 78, 38)),
        (0.60, (189, 151, 79)),
        (0.85, (230, 205, 140)),
        (1.00, (250, 240, 210)),
    ],
    "Snow": [
        (0.00, (80, 80, 90)),
        (0.40, (150, 150, 165)),
        (0.75, (225, 225, 235)),
        (1.00, (255, 255, 255)),
    ],
    "Volcano": [
        (0.00, (20, 18, 18)),
        (0.40, (70, 55, 45)),
        (0.70, (120, 95, 65)),
        (0.90, (170, 150, 120)),
        (1.00, (225, 215, 200)),
    ],
    # Палитра для воды
    "_Water": [
        (0.0, (10, 20, 60)),  # Глубокий океан
        (1.0, (40, 80, 150)),  # Мелководье
    ]
}


def make_colormap_from_palette(name: str) -> Colormap:
    stops = PALETTES.get(name) or PALETTES["Rock"]
    pos = [p for p, _ in stops]
    rgb = [[c / 255.0 for c in col] for _, col in stops]
    return Colormap(rgb, controls=pos)


def map_palette_cpu(
        z01: np.ndarray,
        name: str,
        sea_level_pct: Optional[float] = None
) -> np.ndarray:
    """
    Перевод нормализованных высот z∈[0,1] в RGB.
    Если sea_level_pct задан, все что ниже - красится в цвет воды.
    """
    z = np.clip(z01, 0.0, 1.0).astype(np.float32, copy=False)
    rgb = np.zeros((*z.shape, 3), dtype=np.float32)
    is_land = np.ones_like(z, dtype=bool)

    # 1. Раскрашиваем воду, если нужно
    if sea_level_pct is not None and sea_level_pct > 0.0:
        is_water = z < sea_level_pct
        is_land = ~is_water

        if np.any(is_water):
            water_depth_norm = z[is_water] / sea_level_pct
            stops_water = PALETTES["_Water"]
            xs_water = np.array([p for p, _ in stops_water], dtype=np.float32)
            cols_water = np.array([[r, g, b] for _, (r, g, b) in stops_water], dtype=np.float32) / 255.0

            idx_w = np.searchsorted(xs_water, water_depth_norm, side="right")
            idx0_w, idx1_w = np.clip(idx_w - 1, 0, len(xs_water) - 1), np.clip(idx_w, 0, len(xs_water) - 1)
            x0_w, x1_w = xs_water[idx0_w], xs_water[idx1_w]
            c0_w, c1_w = cols_water[idx0_w], cols_water[idx1_w]
            denom_w = np.maximum(x1_w - x0_w, 1e-6)
            t_w = (water_depth_norm - x0_w) / denom_w

            rgb[is_water] = c0_w * (1.0 - t_w)[..., None] + c1_w * t_w[..., None]

    # 2. Раскрашиваем сушу
    if np.any(is_land):
        if sea_level_pct is not None and (1.0 - sea_level_pct) > 1e-6:
            land_height_norm = (z[is_land] - sea_level_pct) / (1.0 - sea_level_pct)
        else:
            land_height_norm = z[is_land]

        stops_land = PALETTES.get(name) or PALETTES["Rock"]
        xs_land = np.array([p for p, _ in stops_land], dtype=np.float32)
        cols_land = np.array([[r, g, b] for _, (r, g, b) in stops_land], dtype=np.float32) / 255.0

        idx = np.searchsorted(xs_land, land_height_norm, side="right")
        idx0, idx1 = np.clip(idx - 1, 0, len(xs_land) - 1), np.clip(idx, 0, len(xs_land) - 1)
        x0, x1 = xs_land[idx0], xs_land[idx1]
        c0, c1 = cols_land[idx0], cols_land[idx1]
        denom = np.maximum(x1 - x0, 1e-6)
        t = (land_height_norm - x0) / denom

        rgb[is_land] = c0 * (1.0 - t)[..., None] + c1 * t[..., None]

    return np.clip(rgb, 0.0, 1.0)