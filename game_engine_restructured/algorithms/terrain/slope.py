from __future__ import annotations
import math
from typing import Tuple
import numpy as np


def _dilate_bool_mask(mask: np.ndarray, radius: int) -> np.ndarray:
    """Мягкая дилатация (квадратное окно Чебышёва) без wrap-around."""
    if radius <= 0:
        return mask
    h, w = mask.shape
    out = mask.copy()
    for dz in range(-radius, radius + 1):
        for dx in range(-radius, radius + 1):
            if dz == 0 and dx == 0:
                continue
            src_y0 = max(0, -dz)
            src_y1 = h - max(0, dz)
            src_x0 = max(0, -dx)
            src_x1 = w - max(0, dx)
            dst_y0 = max(0, dz)
            dst_y1 = h - max(0, -dz)
            dst_x0 = max(0, dx)
            dst_x1 = w - max(0, -dx)
            if src_y0 < src_y1 and src_x0 < src_x1:
                out[dst_y0:dst_y1, dst_x0:dst_x1] |= mask[src_y0:src_y1, src_x0:src_x1]
    return out


def compute_slope_mask(
    height_m: np.ndarray,
    cell_size_m: float,
    angle_threshold_deg: float,
    band_cells: int = 0,
) -> np.ndarray:
    """
    Маска крутых склонов по порогу угла.
    height_m: 2D массив высот (метры)
    cell_size_m: размер клетки (метры)
    angle_threshold_deg: порог угла в градусах (например, 45)
    band_cells: расширение маски на N клеток (дилатация)
    """
    # Центральные разности внутри, односторонние на границах
    # np.gradient вернёт: gy (по строкам = ось Z), gx (по столбцам = ось X)
    gy, gx = np.gradient(height_m.astype(np.float32), cell_size_m)

    # Тангенс угла наклона: sqrt( (dh/dx)^2 + (dh/dz)^2 )
    tan_slope = np.sqrt(gx * gx + gy * gy, dtype=np.float32)

    thr = math.tan(math.radians(float(angle_threshold_deg)))
    mask = tan_slope >= thr

    if band_cells > 0:
        mask = _dilate_bool_mask(mask, int(band_cells))

    return mask
