# Файл: terrain/steps/utils.py
import numpy as np

def smoothstep(edge0: float, edge1: float, x: np.ndarray) -> np.ndarray:
    """GLSL-like smoothstep."""
    e0, e1 = float(edge0), float(edge1)
    if e0 == e1:
        return (x >= e1).astype(np.float32)
    t = np.clip((x - e0) / (e1 - e0), 0.0, 1.0)
    return (t * t * (3.0 - 2.0 * t)).astype(np.float32)