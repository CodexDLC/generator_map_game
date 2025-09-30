# generator_logic/core/postprocessing.py
from __future__ import annotations
import numpy as np
from ..core.normalization import normalize01

def apply_clamp(array: np.ndarray, min_val: float = 0.0, max_val: float = 1.0) -> np.ndarray:
    """Ограничивает значения массива в заданном диапазоне."""
    return np.clip(array, min_val, max_val)

def apply_extend(array: np.ndarray) -> np.ndarray:
    """Растягивает диапазон массива до [0, 1]."""
    return normalize01(array, mode='minmax', clip_after=True)
