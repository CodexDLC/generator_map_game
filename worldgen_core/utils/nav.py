from pathlib import Path

import cv2
import imageio
import numpy as np

from setting.config import GenConfig
from worldgen_core.pipeline import _stitch_height


def _build_navgrid(base: Path, cfg: GenConfig):
    """Очень простой navgrid: блокируем по уклону и воде."""
    H16 = _stitch_height(base, cfg.width, cfg.height, cfg.chunk)

    # --- ИЗМЕНЕНИЕ: Новая логика расчета высоты ---
    # Вычисляем общий диапазон высот, чтобы высота суши была равна land_height_m
    total_height_range = cfg.land_height_m / max(1.0 - cfg.ocean_level, 1e-6)
    Hm = (H16.astype(np.float32) / 65535.0) * total_height_range
    # --- Конец изменений ---

    gy, gx = np.gradient(Hm, cfg.meters_per_pixel, cfg.meters_per_pixel)
    slope = np.degrees(np.arctan(np.hypot(gx, gy)))
    blocked = slope > cfg.navgrid_max_slope_deg
    if cfg.navgrid_block_water:
        # вода по высоте: теперь порог считается от общего диапазона
        water_h_abs = cfg.ocean_level * total_height_range
        blocked |= (Hm <= water_h_abs + 1e-3)

    cell = max(1, int(round(cfg.navgrid_cell_m / cfg.meters_per_pixel)))
    h2, w2 = (Hm.shape[0] // cell) * cell, (Hm.shape[1] // cell) * cell
    B = blocked[:h2, :w2].reshape(h2 // cell, cell, w2 // cell, cell).any(axis=(1, 3)).astype(np.uint8)

    ndir = base / "navgrid"
    ndir.mkdir(exist_ok=True)
    np.save((ndir / f"grid_cell{cfg.navgrid_cell_m:.2f}m.npy").as_posix(), B)
    prev = (B * 255).astype(np.uint8)
    imageio.imwrite((ndir / f"grid_cell{cfg.navgrid_cell_m:.2f}m_preview.png").as_posix(), prev)
    (ndir / "meta.json").write_text(json.dumps({
        "cell_m": cfg.navgrid_cell_m,
        "max_slope_deg": cfg.navgrid_max_slope_deg,
        "block_water": cfg.navgrid_block_water
    }, ensure_ascii=False, indent=2), encoding="utf-8")
