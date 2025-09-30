# generator_logic/core/enhance.py
from __future__ import annotations
import numpy as np
from ..core.normalization import normalize01

def apply_autolevel(array: np.ndarray, p_low: float = 1.0, p_high: float = 99.0) -> np.ndarray:
    """Выполняет авто-уровни, отсекая крайние значения по перцентилям."""
    return normalize01(array, mode='percentile', p_low=p_low, p_high=p_high, clip_after=True)
