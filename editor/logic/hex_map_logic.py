# editor/logic/hex_map_logic.py
from __future__ import annotations
import logging
import math
from typing import Dict, Tuple, Optional, List
import numpy as np

from PySide6 import QtGui
from PIL import Image, ImageDraw
from PIL.ImageQt import ImageQt

from generator_logic.topology.icosa_grid import build_hexplanet
from generator_logic.topology.hex_mask import build_hex_mask
from generator_logic.terrain.global_sphere_noise import global_sphere_noise_wrapper

logger = logging.getLogger(__name__)

# =============================================================================
# math utils
# =============================================================================

def _normalize(v: np.ndarray) -> np.ndarray:
    v = v.astype(np.float32)
    n = np.linalg.norm(v, axis=-1, keepdims=True)
    return v / (n + 1e-12)

def _euler_yaw_pitch_roll_deg(yaw_deg: float, pitch_deg: float, roll_deg: float) -> np.ndarray:
    y = math.radians(float(yaw_deg))
    p = math.radians(float(pitch_deg))
    r = math.radians(float(roll_deg))
    cy, sy = math.cos(y), math.sin(y)
    cp, sp = math.cos(p), math.sin(p)
    cr, sr = math.cos(r), math.sin(r)
    Rz_yaw = np.array([[ cy, -sy, 0.0],
                       [ sy,  cy, 0.0],
                       [0.0,  0.0, 1.0]], dtype=np.float32)
    Rx_pit = np.array([[1.0, 0.0, 0.0],
                       [0.0,  cp, -sp],
                       [0.0,  sp,  cp]], dtype=np.float32)
    Rz_rol = np.array([[ cr, -sr, 0.0],
                       [ sr,  cr, 0.0],
                       [0.0,  0.0, 1.0]], dtype=np.float32)
    return (Rz_yaw @ Rx_pit) @ Rz_rol

def _hex_outline_pts(sz: int) -> List[Tuple[float, float]]:
    Rpix = sz / 2.0
    inner = Rpix - max(2, sz // 24)
    pts = []
    for i in range(6):
        ang = math.radians(60 * i - 30)
        pts.append((Rpix + inner * math.cos(ang), Rpix + inner * math.sin(ang)))
    return pts

# =============================================================================
# planet data (минимум, без развёрток)
# =============================================================================

def build_planet_data(subdivision_level: int) -> dict:
    logger.info(f"Building planet data (subdivision={subdivision_level})")
    try:
        planet = build_hexplanet(f=subdivision_level)
        centers = np.asarray(planet["centers_xyz"], dtype=np.float32)
        return {
            "neighbors":   planet.get("neighbors", []),
            "pent_ids":    planet.get("pent_ids", []),
            "cell_count":  int(centers.shape[0]),
            "centers_xyz": centers,
            "net_xy01":    planet.get("net_xy01"),  # оставим для совместимости
        }
    except Exception as e:
        logger.error("Failed to build planet data", exc_info=True)
        return {}

# =============================================================================
# sphere (hex-globe) renderer
# =============================================================================

def _draw_hex_globe(
    centers_xyz: np.ndarray,
    pent_ids: List[int],
    sphere_params: dict,
    sea_level: float,
    img_size: Tuple[int, int],
    hex_size_px: int,
) -> QtGui.QPixmap:
    W, H = int(img_size[0]), int(img_size[1])
    canvas = Image.new("RGBA", (W, H), (0, 0, 0, 255))

    # Камера/поворот «сферы»
    Rmat = _euler_yaw_pitch_roll_deg(
        float(sphere_params.get("yaw_deg", 0.0)),
        float(sphere_params.get("pitch_deg", 0.0)),
        float(sphere_params.get("roll_deg", 0.0)),
    ).astype(np.float32)

    # Проекция: ортографическая (вписанный круг радиуса R)
    pad = max(4, hex_size_px // 4)
    Rpix = min(W, H) // 2 - pad
    cx, cy = W // 2, H // 2

    Vw = (centers_xyz @ Rmat.T).astype(np.float32)  # (N,3) — повёрнутая сфера
    z = Vw[:, 2]
    vis = (z > 0.0)                                 # только передняя полусфера
    ids = np.where(vis)[0]
    if ids.size == 0:
        return QtGui.QPixmap.fromImage(ImageQt(canvas.convert("RGB")))

    # экранные позиции
    x = Vw[ids, 0]; y = -Vw[ids, 1]                # инвертируем Y для «севера» вверх
    px = (cx + Rpix * x).astype(np.int32)
    py = (cy + Rpix * y).astype(np.int32)

    # Цвета: глобальный шум + лёгкое освещение от «солнца»
    ctx = {'project': {'seed': int(sphere_params.get('seed', 0))}}
    h01 = global_sphere_noise_wrapper(ctx, sphere_params, coords_xyz=Vw[ids]).astype(np.float32)
    if h01.ndim == 2:    # (M,1) → squeeze
        if h01.shape[1] == 1:
            h01 = h01[:, 0]
    h01 = np.clip(0.5 * h01 + 0.5 if (h01.min() < 0 or h01.max() > 1) else h01, 0.0, 1.0)

    sea_color  = np.array([60,  90, 130], dtype=np.float32)
    land_color = np.array([80, 140,  60], dtype=np.float32)

    # свет из направления (в координатах вида)
    light_dir = _normalize(np.array([0.25, 0.5, 1.0], dtype=np.float32))
    ndotl = np.clip((Vw[ids] @ light_dir), 0.0, 1.0).astype(np.float32)
    shade = 0.55 + 0.45 * ndotl

    pent_set = set(int(p) for p in pent_ids)

    # Шаблоны: маска гекса и контур
    mask_np = (build_hex_mask(
        R=hex_size_px, m_px=max(2, hex_size_px // 24),
        feather_px=1, orientation="pointy"
    ) * 255).astype(np.uint8)
    mask_img = Image.fromarray(mask_np, mode="L")

    outline = Image.new("RGBA", (hex_size_px, hex_size_px), (0, 0, 0, 0))
    d = ImageDraw.Draw(outline)
    d.line(_hex_outline_pts(hex_size_px) + [_hex_outline_pts(hex_size_px)[0]], fill=(25, 35, 45, 220), width=2)

    # круговая маска сферы (чтобы край был ровным)
    circle_mask = Image.new("L", (W, H), 0)
    dc = ImageDraw.Draw(circle_mask)
    dc.ellipse([cx - Rpix, cy - Rpix, cx + Rpix, cy + Rpix], fill=255)

    # рисуем дальние сначала, ближние сверху (ортографическая глубина — по z)
    order = np.argsort(z[ids])  # от малого к большому
    for k in order:
        i = int(ids[k])
        tx, ty = int(p
