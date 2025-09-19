import numpy as np

def _gauss_kernel1d(sigma: float) -> np.ndarray:
    r = max(1, int(3.0 * sigma))
    x = np.arange(-r, r + 1, dtype=np.float32)
    k = np.exp(-0.5 * (x / float(sigma)) ** 2)
    k /= np.sum(k)
    return k.astype(np.float32)

def _blur_sep(src: np.ndarray, sigma: float) -> np.ndarray:
    k = _gauss_kernel1d(sigma)
    # по X
    tmp = np.apply_along_axis(lambda m: np.convolve(m, k, mode="same"), axis=1, arr=src)
    # по Y
    out = np.apply_along_axis(lambda m: np.convolve(m, k, mode="same"), axis=0, arr=tmp)
    return out.astype(np.float32)

def anti_ripple(height: np.ndarray, cell_size: float,
                sigma_low: float = 9.0, sigma_high: float = 3.5,
                alpha: float = 0.6, slope_deg_mid: float = 22.0,
                slope_deg_hard: float = 38.0) -> np.ndarray:
    """
    Убирает среднечастотную «волну», сохраняя силуэты.
    sigma_high < sigma_low  → полоса частот ~ [1/s_low .. 1/s_high]
    alpha — сила подавления.
    Плавно выключается на крутых склонах (чтобы не мылить гребни).
    """
    low  = _blur_sep(height, sigma_low)
    mid  = _blur_sep(height, sigma_high)
    ripple = mid - low  # полосовой компонент (волна)

    # оценка уклона
    gx, gy = np.gradient(height, cell_size)
    slope = np.sqrt(gx*gx + gy*gy)  # тангенс угла

    # гейт по уклону: 1 на пологих, 0 на очень крутых
    t1 = np.tan(np.radians(slope_deg_mid))
    t2 = np.tan(np.radians(slope_deg_hard))
    # smoothstep от t1 к t2, инвертированный
    w = np.clip((slope - t1) / max(1e-6, (t2 - t1)), 0.0, 1.0)
    w = w*w*(3.0 - 2.0*w)
    gate = 1.0 - w

    # вычитаем рябь там, где gate≈1 (пологие), и почти не трогаем гребни
    return (height - alpha * ripple * gate).astype(np.float32)
