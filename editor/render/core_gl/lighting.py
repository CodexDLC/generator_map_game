# editor/render/core_gl/lighting.py
"""
Общие вспомогательные функции для расчета освещения.
"""
import math

def get_light_direction_from_angles(az_deg: float, alt_deg: float) -> tuple[float, float, float]:
    """
    Рассчитывает вектор направления ИСТОЧНИКА света (world space)
    по азимуту и высоте.
    (Логика перенесена из region_mesh_builder._dir_from_angles)
    """
    az = math.radians(az_deg)
    alt = math.radians(alt_deg)
    x = math.cos(alt) * math.cos(az)
    y = math.cos(alt) * math.sin(az)
    z = math.sin(alt)
    # Возвращает вектор ОТ источника света
    return (-x, -y, -z)