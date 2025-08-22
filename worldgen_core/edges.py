import numpy as np

def _smoothstep(a, b, x):
    t = np.clip((x - a) / (b - a), 0.0, 1.0)
    return t * t * (3 - 2 * t)

def apply_edge_boost_radial(h01, gx0, gy0, w, h, W, H, edge_boost, edge_margin_frac):
    if edge_boost <= 0 or edge_margin_frac <= 0: return h01
    cx, cy = (W - 1) * 0.5, (H - 1) * 0.5
    xs = np.arange(gx0, gx0 + w); ys = np.arange(gy0, gy0 + h)
    X, Y = np.meshgrid(xs, ys)
    r = np.sqrt((X - cx)**2 + (Y - cy)**2)
    r_norm = r / np.sqrt(cx**2 + cy**2)           # 0 центр → 1 углы
    mask = _smoothstep(1.0 - edge_margin_frac, 1.0, r_norm)
    return np.clip(h01 + edge_boost * mask, 0.0, 1.0)

def to_uint16(height01):
    import numpy as np
    arr = np.clip(height01, 0.0, 1.0)
    return np.round(arr * 65535.0).astype(np.uint16)
