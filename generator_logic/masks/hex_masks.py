# generator_logic/masks/hex_masks.py
from __future__ import annotations
import numpy as np


def smoothstep(edge0: float, edge1: float, x: np.ndarray) -> np.ndarray:
    """GLSL-like smoothstep."""
    e0, e1 = float(edge0), float(edge1)
    if e0 == e1:
        return (x >= e1).astype(np.float32)
    t = np.clip((x - e0) / (e1 - e0), 0.0, 1.0)
    return (t * t * (3.0 - 2.0 * t)).astype(np.float32)


def create_radial_hex_mask(shape: tuple[int, int]) -> np.ndarray:
    """
    Создает маску [0,1] в виде гексагона, вписанного в квадратный массив.

    Маска имеет значение 1.0 внутри вписанной окружности гексагона,
    плавно переходит в 0.0 в зоне между вписанной и описанной окружностями.
    """
    h, w = shape
    if h != w:
        raise ValueError("Функция create_radial_hex_mask ожидает квадратную форму.")

    # Создаем сетку координат от -1 до 1 с центром в (0,0)
    x = np.linspace(-1.0, 1.0, w, dtype=np.float32)
    y = np.linspace(-1.0, 1.0, h, dtype=np.float32)
    xv, yv = np.meshgrid(x, y)

    # 1. Радиус описанной окружности (до вершин гексагона)
    # В нашей системе координат от -1 до 1, он равен 1.0
    outer_radius = 1.0

    # 2. Радиус вписанной окружности (до центра ребер гексагона)
    # Он равен R * cos(30°) или R * sqrt(3)/2
    inner_radius = outer_radius * (np.sqrt(3.0) / 2.0)

    # 3. Вычисляем евклидово расстояние от центра для каждого пикселя
    distance_from_center = np.sqrt(xv ** 2 + yv ** 2)

    # 4. Используем smoothstep для создания плавного перехода
    # Формула инвертирована (1.0 - ...), чтобы в центре был 1, а по краям 0.
    mask = 1.0 - smoothstep(inner_radius, outer_radius, distance_from_center)

    return mask.astype(np.float32)