# game_engine_restructured/world/planetary_grid.py
from __future__ import annotations
import numpy as np
from typing import Tuple

# Константы для икосаэдра
X = 0.525731112119133606
Z = 0.850650808352039932

# 12 вершин икосаэдра
ICO_VERTICES = np.array([
    [-X, 0.0, Z], [X, 0.0, Z], [-X, 0.0, -Z], [X, 0.0, -Z],
    [0.0, Z, X], [0.0, Z, -X], [0.0, -Z, X], [0.0, -Z, -X],
    [Z, X, 0.0], [-Z, X, 0.0], [Z, -X, 0.0], [-Z, -X, 0.0]
], dtype=np.float32)

# 20 граней (треугольников), определенных через индексы вершин
ICO_FACES = np.array([
    [0, 4, 1], [0, 9, 4], [9, 5, 4], [4, 5, 8], [4, 8, 1],
    [8, 10, 1], [8, 3, 10], [5, 3, 8], [5, 2, 3], [2, 7, 3],
    [7, 10, 3], [7, 6, 10], [7, 11, 6], [11, 0, 6], [0, 1, 6],
    [6, 1, 10], [9, 0, 11], [9, 11, 2], [9, 2, 5], [7, 2, 11]
], dtype=np.int32)


class PlanetaryGrid:
    """
    Управляет логической сеткой планеты на основе икосаэдра.
    Отвечает за преобразование координат из 2D "развертки" в 3D пространство на сфере.
    """

    def __init__(self, radius_m: float):
        self.radius = float(radius_m)

    def get_face_transform(self, face_index: int) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Возвращает базисные векторы для указанной грани икосаэдра.
        Это позволяет нам "развернуть" треугольную грань на плоскость.
        """
        # --- НАЧАЛО ИСПРАВЛЕНИЯ ---
        # Гарантируем, что индекс всегда будет в допустимом диапазоне [0, 19]
        safe_index = face_index % len(ICO_FACES)
        if not (0 <= safe_index < len(ICO_FACES)):
            raise ValueError("Неверный индекс грани икосаэдра.")

        p0_idx, p1_idx, p2_idx = ICO_FACES[safe_index]
        # --- КОНЕЦ ИСПРАВЛЕНИЯ ---

        p0, p1, p2 = ICO_VERTICES[p0_idx], ICO_VERTICES[p1_idx], ICO_VERTICES[p2_idx]

        origin = p0
        basis_u = p1 - p0
        basis_v = p2 - p0

        return origin, basis_u, basis_v

    def map_plane_to_sphere(self, face_index: int, u: np.ndarray, v: np.ndarray) -> np.ndarray:
        """
        Основная функция. Преобразует 2D координаты (u, v) с плоского
        треугольника (грани) в 3D координаты (X, Y, Z) на поверхности сферы.
        - u, v: 2D массивы координат в диапазоне [0, 1] на плоскости грани.
        """
        origin, basis_u, basis_v = self.get_face_transform(face_index)

        # Интерполируем точку на плоскости треугольника в 3D
        points_3d = origin + u[..., np.newaxis] * basis_u + v[..., np.newaxis] * basis_v

        # Нормализуем вектор, чтобы "спроецировать" точку на сферу
        norm = np.linalg.norm(points_3d, axis=-1, keepdims=True)
        points_on_sphere = points_3d / np.maximum(norm, 1e-9)

        # Масштабируем до радиуса планеты
        return (points_on_sphere * self.radius).astype(np.float32)

    def get_coords_for_region(self, region_id: int, resolution: int) -> np.ndarray:
        """
        Генерирует квадратную сетку 3D-координат для указанного региона.
        - region_id: сейчас просто индекс грани икосаэдра (0-19).
        - resolution: размер квадратного "полотна" (например, 1024).
        """
        # Создаем плоскую сетку 2D-координат для нашего квадрата
        # u и v будут меняться от 0 до 1
        u_flat = np.linspace(0, 1, resolution, dtype=np.float32)
        v_flat = np.linspace(0, 1, resolution, dtype=np.float32)
        u, v = np.meshgrid(u_flat, v_flat)

        # Используем маску, чтобы работать только с точками внутри треугольника
        # (Оптимизация: пока генерируем для всего квадрата, маску можно применить позже)
        # valid_mask = (u + v) <= 1.0

        # Преобразуем 2D сетку в 3D координаты на сфере
        coords_3d = self.map_plane_to_sphere(region_id, u, v)

        return coords_3d