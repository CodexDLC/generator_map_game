# game_engine_restructured/algorithms/terrain/slope.py
from __future__ import annotations
import math
import numpy as np
from numba import prange, njit


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


@njit(cache=True, fastmath=True, parallel=True)
def apply_slope_limiter(heights: np.ndarray, max_slope_tangent: float, cell_size: float, iterations: int):
    """
    Итеративно ограничивает уклон: |∇h| <= tan(theta_max).
    Делается двумя независимыми проходами: по строкам и по столбцам.
    Внутри прохода корректируются непересекающиеся пары (even/odd), чтобы не было конфликтов записи.

    Порог между соседями по оси берём пониженный: Δh_axis = tan(theta_max) * s / sqrt(2),
    чтобы суммарный модуль градиента (по двум осям) не превышал tan(theta_max).
    """
    H, W = heights.shape
    # Осевой порог (см. комментарий выше)
    delta_axis = (max_slope_tangent * cell_size) / math.sqrt(2.0)

    for _ in range(iterations):
        # ---------------------
        # Горизонтальный проход: строки независимы → параллелим по строкам
        # ---------------------
        for z in prange(H):
            # even пары: (0,1), (2,3), ...
            x = 0
            while x + 1 < W:
                diff = heights[z, x] - heights[z, x + 1]
                if diff >  delta_axis:
                    corr = 0.5 * (diff - delta_axis)
                    heights[z, x]     -= corr
                    heights[z, x + 1] += corr
                elif diff < -delta_axis:
                    corr = 0.5 * (-delta_axis - diff)
                    heights[z, x]     += corr
                    heights[z, x + 1] -= corr
                x += 2

            # odd пары: (1,2), (3,4), ...
            x = 1
            while x + 1 < W:
                diff = heights[z, x] - heights[z, x + 1]
                if diff >  delta_axis:
                    corr = 0.5 * (diff - delta_axis)
                    heights[z, x]     -= corr
                    heights[z, x + 1] += corr
                elif diff < -delta_axis:
                    corr = 0.5 * (-delta_axis - diff)
                    heights[z, x]     += corr
                    heights[z, x + 1] -= corr
                x += 2

        # ---------------------
        # Вертикальный проход: столбцы независимы → параллелим по столбцам
        # ---------------------
        for x in prange(W):
            # even пары: (0,1), (2,3), ...
            z = 0
            while z + 1 < H:
                diff = heights[z, x] - heights[z + 1, x]
                if diff >  delta_axis:
                    corr = 0.5 * (diff - delta_axis)
                    heights[z, x]       -= corr
                    heights[z + 1, x]   += corr
                elif diff < -delta_axis:
                    corr = 0.5 * (-delta_axis - diff)
                    heights[z, x]       += corr
                    heights[z + 1, x]   -= corr
                z += 2

            # odd пары: (1,2), (3,4), ...
            z = 1
            while z + 1 < H:
                diff = heights[z, x] - heights[z + 1, x]
                if diff >  delta_axis:
                    corr = 0.5 * (diff - delta_axis)
                    heights[z, x]       -= corr
                    heights[z + 1, x]   += corr
                elif diff < -delta_axis:
                    corr = 0.5 * (-delta_axis - diff)
                    heights[z, x]       += corr
                    heights[z + 1, x]   -= corr
                z += 2

    return heights