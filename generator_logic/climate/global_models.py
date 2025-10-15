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

    Args:
        xyz_coords: Массив (N, 3) нормализованных 3D-координат точек на сфере.
        base_temp_c: Средняя температура на экваторе.
        equator_pole_temp_diff_c: Разница температур между экватором и полюсом.

    Returns:
        1D-массив температур для каждой точки.
    """
    # Y-координата в нормализованном пространстве [-1, 1] соответствует синусу широты.
    # 1.0 - на северном полюсе, -1.0 - на южном.
    latitude_factor = np.abs(xyz_coords[:, 1])  # от 0 (экватор) до 1 (полюса)

    # Линейно интерполируем температуру
    temperature = base_temp_c - latitude_factor * equator_pole_temp_diff_c

    return temperature.astype(np.float32)