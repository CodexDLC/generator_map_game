# editor/vis/mesh_from_height.py
import numpy as np


# НОВАЯ, НАДЕЖНАЯ ВЕРСИЯ ФУНКЦИИ
# НОВАЯ, НАДЕЖНАЯ ВЕРСИЯ ФУНКЦИИ
def mesh_from_height(z_map: np.ndarray, cell_size: float = 1.0, x0: float = 0.0, y0: float = 0.0) -> tuple[
    np.ndarray, np.ndarray, np.ndarray]:
    """
    Создает меш (вершины и грани) из 2D карты высот.
    """
    h, w = z_map.shape
    x = np.linspace(x0, x0 + (w - 1) * cell_size, w)
    y = np.linspace(y0, y0 + (h - 1) * cell_size, h)
    xx, yy = np.meshgrid(x, y)

    # Создаем вершины: (x, y, z)
    vertices = np.stack([xx.ravel(), yy.ravel(), z_map.ravel()], axis=1)

    # Создаем индексы для граней
    # i, j --- левый верхний угол квадрата
    i, j = np.mgrid[0:h - 1, 0:w - 1]

    # Индексы вершин для каждого квадрата
    idx0 = i * w + j  # Левый верхний
    idx1 = i * w + (j + 1)  # Правый верхний
    idx2 = (i + 1) * w + j  # Левый нижний
    idx3 = (i + 1) * w + (j + 1)  # Правый нижний

    # Два треугольника на каждый квадрат
    faces1 = np.stack([idx0.ravel(), idx2.ravel(), idx1.ravel()], axis=1)
    faces2 = np.stack([idx1.ravel(), idx2.ravel(), idx3.ravel()], axis=1)

    faces = np.vstack([faces1, faces2])

    # UV-координаты (здесь просто для совместимости)
    uv = vertices[:, :2] / np.array([xx.max(), yy.max()])

    return vertices.astype(np.float32), faces.astype(np.uint32), uv.astype(np.float32)