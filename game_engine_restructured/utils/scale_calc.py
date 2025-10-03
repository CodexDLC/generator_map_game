# game_engine_restructured/utils/scale_calc.py
import math
from dataclasses import dataclass

@dataclass
class HexScale:
    N: int                    # общее число регионов
    theta_eq: float           # ср. угловой радиус клетки (рад)
    r_px: float               # пиксельный радиус гекса
    W_total_px: float         # ширина полотна 360° (px) при данном alpha
    H_total_px: float         # высота полотна (px)
    hex_width_px: float       # ширина гекса по "флэтам" (px) ~ sqrt(3)*r_px
    hex_height_px: float      # высота гекса по "углам" (px) = 2*r_px

def compute_hex_scale(f: int, R: int, rho: float, alpha: float) -> HexScale:
    """
    f     : частота деления (напр. 8)
    R     : размер квадратного тайла региона (px) — 1024/2048/4096
    rho   : доля тайла под "ядро" гекса (типично ~0.34, но регулируется)
    alpha : множитель шага между центрами (>=1.0 для большего межзонья)

    Возвращает все главные px-величины. Физику считай отдельно через MPP.
    """
    assert f >= 1 and R > 0 and rho > 0 and alpha > 0
    N = 10 * f * f + 2
    theta_eq = 2.0 / math.sqrt(N)  # радиан
    r_px = rho * float(R)
    W_total_px = (2.0 * math.pi * alpha * r_px) / theta_eq
    H_total_px = 0.5 * W_total_px
    return HexScale(
        N=N,
        theta_eq=theta_eq,
        r_px=r_px,
        W_total_px=W_total_px,
        H_total_px=H_total_px,
        hex_width_px=math.sqrt(3.0) * r_px,
        hex_height_px=2.0 * r_px,
    )

def meters_per_pixel_for_target_circumference_km(W_total_px: float, target_C_km: float) -> float:
    """Подобрать MPP, чтобы экватор имел заданную длину (км)."""
    return (target_C_km * 1000.0) / W_total_px

def meters_per_pixel_for_target_cell_width_m(hex_width_px: float, target_cell_width_m: float) -> float:
    """Подобрать MPP, чтобы один гекс имел заданную ширину по флэтам (м)."""
    return target_cell_width_m / hex_width_px
