# generator_logic/climate/global_models.py
from __future__ import annotations
import numpy as np

def calculate_base_temperature(
    xyz_coords: np.ndarray,
    base_temp_c: float,
    equator_pole_temp_diff_c: float
) -> np.ndarray:
    """
    Рассчитывает базовую температуру на сфере в зависимости от широты.
    """
    # Z-координата (индекс 2) в нормализованном пространстве [-1, 1] соответствует синусу широты.
    latitude_factor = np.abs(xyz_coords[:, 2])  # от 0 (экватор) до 1 (полюса)

    temperature = base_temp_c - latitude_factor * equator_pole_temp_diff_c
    return temperature.astype(np.float32)