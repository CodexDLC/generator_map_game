import numpy as np


def _smoothstep(a, b, x):
    """Плавная S-образная интерполяция."""
    # Масштабируем x, чтобы он был в диапазоне [0, 1]
    t = np.clip((x - a) / (b - a), 0.0, 1.0)
    # Применяем формулу smoothstep
    return t * t * (3 - 2 * t)


def apply_edge_falloff(h, cx, cy, cols, rows, width_px=256, ocean=0.5, power=1.8):
    import numpy as np
    H, W = h.shape
    gx0, gy0 = cx*W, cy*H
    X = np.arange(gx0, gx0+W)[None, :]
    Y = np.arange(gy0, gy0+H)[:, None]
    max_x, max_y = cols*W - 1, rows*H - 1
    dx = np.minimum(X - 0, max_x - X)
    dy = np.minimum(Y - 0, max_y - Y)
    dist = np.minimum(dx, dy).astype(np.float32)
    w = max(float(width_px), 1.0)
    t = np.clip(dist / w, 0.0, 1.0)
    f = (t*t*(3-2*t)) ** power          # smoothstep^power
    return ocean + (h - ocean) * f


def to_uint16(height01):
    import numpy as np
    arr = np.clip(height01, 0.0, 1.0)
    return np.round(arr * 65535.0).astype(np.uint16)