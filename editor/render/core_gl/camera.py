# editor/render/core_gl/camera.py
"""
Общий класс Turntable-камеры для QOpenGLWidget.
(Модифицирован для поддержки двух режимов вращения)
"""
from __future__ import annotations
import math
import numpy as np
from PySide6 import QtCore, QtGui


class TurntableCamera:
    def __init__(self, fov: float = 45.0, distance: float = 2.5, mode: str = 'trackball'):
        self._cam_distance = distance
        self._last_mouse_pos = QtCore.QPoint()

        self._width = 1
        self._height = 1
        self._fov = fov
        self._center = QtGui.QVector3D(0, 0, 0)

        # --- ИЗМЕНЕНИЕ: Добавляем режим и переменные для него ---
        self._mode = mode

        # Для 'trackball'
        self._rotation = QtGui.QQuaternion()

        # Для 'z_up_turntable' (значения по умолчанию из старого vispy)
        self._azimuth = 45.0
        self._elevation = 30.0
        # ---------------------------------------------------

    def set_viewport(self, w: int, h: int):
        self._width = max(1, w)
        self._height = max(1, h)

    def set_fov(self, fov: float):
        self._fov = fov

    def set_range(self, x_range: tuple[float, float], y_range: tuple[float, float], z_range: tuple[float, float]):
        center_x = (x_range[0] + x_range[1]) / 2.0
        center_y = (y_range[0] + y_range[1]) / 2.0
        center_z = (z_range[0] + z_range[1]) / 2.0
        self._center = QtGui.QVector3D(center_x, center_y, center_z)

        size_x = x_range[1] - x_range[0]
        size_y = y_range[1] - y_range[0]

        # Только меняем дистанцию, если она не установлена (для сферы)
        if self._mode == 'z_up_turntable':
            self._cam_distance = 1.8 * max(max(size_x, size_y), abs(z_range[1] - z_range[0]))
            if self._cam_distance == 0: self._cam_distance = 100  # Защита

    def get_projection_matrix(self) -> QtGui.QMatrix4x4:
        proj = QtGui.QMatrix4x4()
        # Увеличиваем far plane для больших карт
        proj.perspective(self._fov, self._width / self._height, 0.1, 20000.0)
        return proj

    def get_camera_matrix(self) -> QtGui.QMatrix4x4:
        """ Матрица только для камеры (без вращения) """
        cam = QtGui.QMatrix4x4()
        cam.translate(0.0, 0.0, -self._cam_distance)
        return cam

    def get_model_view_matrix(self) -> QtGui.QMatrix4x4:
        """ Матрица для модели (камера + вращение + центр) """
        mv = QtGui.QMatrix4x4()
        mv.translate(0.0, 0.0, -self._cam_distance)

        # --- ИЗМЕНЕНИЕ: Разная логика вращения ---
        if self._mode == 'trackball':
            mv.rotate(self._rotation)
        elif self._mode == 'z_up_turntable':
            # Сначала наклон (вокруг X), потом азимут (вокруг Z)
            mv.rotate(self._elevation, 1, 0, 0)
            mv.rotate(self._azimuth, 0, 0, 1)
        # ----------------------------------------

        mv.translate(-self._center)  # Смещаем, чтобы вращаться вокруг центра меша
        return mv

    # --- Обработчики событий ---

    def handle_mouse_press(self, event: QtGui.QMouseEvent):
        self._last_mouse_pos = event.position().toPoint()

    def handle_mouse_move(self, event: QtGui.QMouseEvent) -> bool:
        """ Возвращает True, если камера обновилась """
        dx = event.position().toPoint().x() - self._last_mouse_pos.x()
        dy = event.position().toPoint().y() - self._last_mouse_pos.y()

        if not (event.buttons() & QtCore.Qt.MouseButton.LeftButton):
            self._last_mouse_pos = event.position().toPoint()
            return False

        # --- ИЗМЕНЕНИЕ: Разная логика вращения ---
        if self._mode == 'trackball':
            axis = QtGui.QVector3D(dy, dx, 0.0).normalized()
            angle = math.sqrt(dx * dx + dy * dy) * 0.5
            self._rotation = QtGui.QQuaternion.fromAxisAndAngle(axis, angle) * self._rotation

        elif self._mode == 'z_up_turntable':
            # dx меняет азимут (вокруг Z), dy меняет высоту (вокруг X)
            self._azimuth += dx * 0.5
            self._elevation += dy * 0.5
            # Ограничиваем наклон, чтобы не перевернуться
            self._elevation = max(-89.9, min(89.9, self._elevation))
        # ----------------------------------------

        self._last_mouse_pos = event.position().toPoint()
        return True

    def handle_wheel(self, event: QtGui.QWheelEvent) -> bool:
        """ Возвращает True, если камера обновилась """
        # --- ИЗМЕНЕНИЕ: Более быстрый зум для Z-Up ---
        if self._mode == 'z_up_turntable':
            # Процентный зум
            delta = -event.angleDelta().y() / 1200.0
            new_distance = self._cam_distance * (1.0 + delta * 5.0)
        else:
            # Фиксированный зум (для сферы)
            new_distance = self._cam_distance - event.angleDelta().y() / 240.0

        min_dist = 0.1 if self._mode == 'z_up_turntable' else 1.1
        max_dist = 10000.0 if self._mode == 'z_up_turntable' else 10.0

        if abs(new_distance - self._cam_distance) > 1e-6:
            self._cam_distance = max(min_dist, min(new_distance, max_dist))
            return True
        return False