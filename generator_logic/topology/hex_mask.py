# generator_logic/topology/hex_mask.py
from __future__ import annotations
import math
import numpy as np

SQRT3 = math.sqrt(3.0)

def _hex_vertices(center_x: float, center_y: float, r: float, orientation: str) -> np.ndarray:
    """
    Возвращает 6 вершин гекса (CCW), центр в (cx,cy), circumradius=r.
    orientation: "pointy" (вершина вверх) или "flat" (плоский верх).
    """
    cx, cy = center_x, center_y
    if orientation == "flat":
        # плоская верхушка: первый угол 0° (вправо), шаг 60°
        angles = [0, 60, 120, 180, 240, 300]
    else:
        # pointy-top: первая вершина вверх (90°), шаг 60°
        angles = [90, 150, 210, 270, 330, 30]
    verts = []
    for a in angles:
        rad = math.radians(a)
        verts.append([cx + r * math.cos(rad), cy + r * math.sin(rad)])
    return np.asarray(verts, dtype=np.float32)  # (6,2)

def _point_in_convex_polygon(px: np.ndarray, py: np.ndarray, poly: np.ndarray) -> np.ndarray:
    """
    Векторная проверка точки внутри выпуклого многоугольника (CCW).
    px,py формы (H,W). poly формы (N,2).
    Возвращает bool-маску (H,W).
    """
    H, W = px.shape
    inside = np.ones((H, W), dtype=bool)
    for i in range(len(poly)):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % len(poly)]
        # вектор ребра
        ex, ey = (x2 - x1), (y2 - y1)
        # вектор из вершины к точке
        vx, vy = (px - x1), (py - y1)
        # z-компонента псевдоскалярного произведения (ex,ey)x(vx,vy) = ex*vy - ey*vx
        cross = ex * vy - ey * vx
        # для CCW: все cross >= 0 -> внутри
        inside &= (cross >= 0.0)
    return inside

def _distance_to_edges(px: np.ndarray, py: np.ndarray, poly: np.ndarray) -> np.ndarray:
    """
    Минимальная евклидова дистанция до рёбер многоугольника (в пикселях), форма (H,W).
    """
    H, W = px.shape
    min_dist2 = np.full((H, W), np.inf, dtype=np.float32)
    for i in range(len(poly)):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % len(poly)]
        ex, ey = (x2 - x1), (y2 - y1)
        elen2 = ex*ex + ey*ey + 1e-12
        # проекция точки на отрезок в параметре t∈[0,1]
        t = ((px - x1)*ex + (py - y1)*ey) / elen2
        t = np.clip(t, 0.0, 1.0)
        nx = x1 + t * ex
        ny = y1 + t * ey
        dx = px - nx
        dy = py - ny
        d2 = dx*dx + dy*dy
        min_dist2 = np.minimum(min_dist2, d2.astype(np.float32))
    return np.sqrt(min_dist2, dtype=np.float32)

def build_hex_mask(R: int,
                   m_px: int = 24,
                   feather_px: int = 24,
                   orientation: str = "pointy") -> np.ndarray:
    """
    Возвращает 2D-маску (R,R) float32 в [0..1]:
      1.0 в центре гекса,
      плавно спадает к 0 на перье шириной feather_px,
      за пределами гекса -> 0.
    Гекс вписан в квадрат с отступом m_px.
    """
    assert R > 0 and m_px >= 0 and feather_px >= 0
    # Радиус гекса (circumradius) с учётом перышка
    r = (R - 2*m_px) * 0.5 - float(feather_px)
    if r <= 1.0:
        r = max(1.0, (R - 2.0) * 0.25)  # страховка

    cx = cy = (R - 1) * 0.5  # центр пиксельной сетки
    verts = _hex_vertices(cx, cy, r, orientation)
    # Сетка координат
    ys, xs = np.mgrid[0:R, 0:R]
    xs = xs.astype(np.float32)
    ys = ys.astype(np.float32)

    inside = _point_in_convex_polygon(xs, ys, verts)
    dist  = _distance_to_edges(xs, ys, verts)  # >=0

    # Signed distance: внутри отрицательное, снаружи положительное
    sd = dist.copy()
    sd[inside] *= -1.0

    # Плавный край: 1 внутри, 0 снаружи; переход на полосе шириной feather_px
    w = float(feather_px) + 1e-6
    # smoothstep: 1 - smoothstep(0, w, max(sd,0)) не даёт "ступеньки" на границе
    # но нам нужен плавный переход именно от -w до 0
    t = np.clip((sd + w) / w, 0.0, 1.0)  # sd=-w -> 0; sd=0 -> 1
    mask = 1.0 - t                      # внутри ~1, к границе падает к 0

    # Вырезаем всё, что за пределами внешней границы гекса
    mask[sd > 0.0] = 0.0
    return mask.astype(np.float32)
