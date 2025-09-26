import numpy as np

def hillshade(heightmap: np.ndarray, azimuth: float = 315.0, altitude: float = 45.0) -> np.ndarray:
    """Возвращает [0..1] карту затенения по рельефу (как в GIS)."""
    z = heightmap.astype(np.float32, copy=False)
    # градиенты: x — на восток, y — на север (не критично, лишь бы последовательно)
    gy, gx = np.gradient(z)   # порядок (rows, cols) → gy = d/drow, gx = d/dcol
    slope = np.pi/2.0 - np.arctan(np.hypot(gx, gy))
    aspect = np.arctan2(-gx, gy)

    az = np.radians(azimuth)
    alt = np.radians(altitude)

    shaded = np.sin(alt)*np.sin(slope) + np.cos(alt)*np.cos(slope)*np.cos(az - aspect)
    shaded = (shaded - shaded.min()) / max(1e-6, (shaded.max() - shaded.min()))
    return shaded
