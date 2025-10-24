# editor/render/sphere_preview_widget.py
from __future__ import annotations
import logging
import math
import numpy as np
from PySide6 import QtCore, QtGui
from PySide6.QtOpenGLWidgets import QOpenGLWidget
from OpenGL import GL
from OpenGL.GL import *

from editor.core.render_settings import RenderSettings
from generator_logic.topology.icosa_grid import nearest_cell_by_xyz

from editor.render.core_gl import shader_library, shader_manager, lighting
# --- ДОБАВЛЕН ИМПОРТ КАМЕРЫ ---
from editor.render.core_gl.camera import TurntableCamera

logger = logging.getLogger(__name__)


class SpherePreviewWidget(QOpenGLWidget):
    cell_picked = QtCore.Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(512, 256)
        self._shader_program = None

        self._vbo_pos, self._vbo_col, self._ibo_fill, self._ibo_lines = None, None, None, None

        self._vertices = np.array([], dtype=np.float32)
        self._colors = np.array([], dtype=np.float32)
        self._fill_indices = np.array([], dtype=np.uint32)
        self._line_indices = np.array([], dtype=np.uint32)
        self._planet_data = None
        self._render_settings = RenderSettings()

        # --- ИЗМЕНЕНИЕ: Управлением камерой занимается отдельный класс ---
        self._camera = TurntableCamera(fov=45.0, distance=2.5, mode='trackball')

        self._poles_shader_program = None
        self._poles_vbo_pos = None
        self._poles_vbo_col = None

    def set_render_settings(self, settings: RenderSettings):
        self._render_settings = settings
        self._camera.set_fov(settings.fov)
        self.update()

    def set_planet_data(self, data: dict):
        self._planet_data = data

    def set_geometry(self, vertices: np.ndarray, fill_indices: np.ndarray, line_indices: np.ndarray,
                     colors: np.ndarray):
        self.makeCurrent()
        if self._vbo_pos is not None:
            GL.glDeleteBuffers(4, [self._vbo_pos, self._vbo_col, self._ibo_fill, self._ibo_lines])
        self._vbo_pos, self._vbo_col, self._ibo_fill, self._ibo_lines = None, None, None, None

        self._vertices = vertices if vertices is not None else np.array([], dtype=np.float32)
        self._colors = colors if colors is not None else np.array([], dtype=np.float32)
        self._fill_indices = fill_indices if fill_indices is not None else np.array([], dtype=np.uint32)
        self._line_indices = line_indices if line_indices is not None else np.array([], dtype=np.uint32)

        self._camera.set_range(x_range=(-1, 1), y_range=(-1, 1), z_range=(-1, 1))

        self.doneCurrent()
        self.update()

    def initializeGL(self):
        # (Код без изменений)
        vs = shader_manager.compile_shader(GL_VERTEX_SHADER, shader_library.VS_CODE)
        fs = shader_manager.compile_shader(GL_FRAGMENT_SHADER, shader_library.FS_CODE)
        self._shader_program = shader_manager.link_program(vs, fs)
        if not self._shader_program:
            logger.error("Не удалось слинковать основную программу шейдеров!")
            return
        # (Код для полюсов без изменений)
        vs_poles = shader_manager.compile_shader(GL_VERTEX_SHADER, shader_library.VS_POLES_CODE)
        fs_poles = shader_manager.compile_shader(GL_FRAGMENT_SHADER, shader_library.FS_POLES_CODE)
        self._poles_shader_program = shader_manager.link_program(vs_poles, fs_poles)
        if not self._poles_shader_program:
            logger.error("Не удалось слинковать программу шейдеров полюсов!")
            return
        pole_positions = np.array([[0, 0, 1.02], [0, 0, -1.02]], dtype=np.float32)
        pole_colors = np.array([[1, 0, 0], [0, 0, 1]], dtype=np.float32)
        self._poles_vbo_pos = GL.glGenBuffers(1)
        GL.glBindBuffer(GL_ARRAY_BUFFER, self._poles_vbo_pos)
        GL.glBufferData(GL_ARRAY_BUFFER, pole_positions.nbytes, pole_positions, GL_STATIC_DRAW)
        self._poles_vbo_col = GL.glGenBuffers(1)
        GL.glBindBuffer(GL_ARRAY_BUFFER, self._poles_vbo_col)
        GL.glBufferData(GL_ARRAY_BUFFER, pole_colors.nbytes, pole_colors, GL_STATIC_DRAW)
        GL.glEnable(GL_DEPTH_TEST)
        GL.glEnable(GL_CULL_FACE)
        GL.glEnable(GL_POLYGON_OFFSET_FILL)
        GL.glPolygonOffset(1.0, 1.0)
        GL.glEnable(GL_PROGRAM_POINT_SIZE)
        GL.glClearColor(0.1, 0.1, 0.15, 1.0)

    def paintGL(self):
        GL.glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)

        # --- ИЗМЕНЕНИЕ: Получаем матрицы из камеры ---
        camera_matrix = self._camera.get_camera_matrix()
        model_view_matrix = self._camera.get_model_view_matrix()
        proj_matrix = self._camera.get_projection_matrix()
        mvp = proj_matrix * model_view_matrix
        # -------------------------------------

        # --- 1. РИСУЕМ ПЛАНЕТУ ---
        if self._shader_program and self._vertices.size > 0:
            if self._vbo_pos is None:
                # (Код VBO без изменений)
                self._vbo_pos = GL.glGenBuffers(1)
                GL.glBindBuffer(GL_ARRAY_BUFFER, self._vbo_pos)
                GL.glBufferData(GL_ARRAY_BUFFER, self._vertices.nbytes, self._vertices, GL_STATIC_DRAW)
                self._vbo_col = GL.glGenBuffers(1)
                GL.glBindBuffer(GL_ARRAY_BUFFER, self._vbo_col)
                GL.glBufferData(GL_ARRAY_BUFFER, self._colors.nbytes, self._colors, GL_STATIC_DRAW)
                self._ibo_fill = GL.glGenBuffers(1)
                GL.glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, self._ibo_fill)
                GL.glBufferData(GL_ELEMENT_ARRAY_BUFFER, self._fill_indices.nbytes, self._fill_indices, GL_STATIC_DRAW)
                self._ibo_lines = GL.glGenBuffers(1)
                GL.glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, self._ibo_lines)
                GL.glBufferData(GL_ELEMENT_ARRAY_BUFFER, self._line_indices.nbytes, self._line_indices, GL_STATIC_DRAW)

            GL.glUseProgram(self._shader_program)

            # (Логика освещения без изменений)
            s = self._render_settings
            light_dir_world = lighting.get_light_direction_from_angles(s.light_azimuth_deg, s.light_altitude_deg)
            ldw_vec3 = QtGui.QVector3D(light_dir_world[0], light_dir_world[1], light_dir_world[2])
            light_dir_view_vec4 = camera_matrix.map(QtGui.QVector4D(ldw_vec3, 0.0))
            light_dir_view = light_dir_view_vec4.toVector3D().normalized()
            GL.glUniform3f(GL.glGetUniformLocation(self._shader_program, "u_light_dir_view"), light_dir_view.x(),
                           light_dir_view.y(), light_dir_view.z())
            GL.glUniform1f(GL.glGetUniformLocation(self._shader_program, "u_ambient"), s.ambient)
            GL.glUniform1f(GL.glGetUniformLocation(self._shader_program, "u_diffuse"), s.diffuse)

            # --- ИЗМЕНЕНИЕ: Говорим шейдеру, что это сфера ---
            GL.glUniform1i(GL.glGetUniformLocation(self._shader_program, "u_is_sphere"), GL_TRUE)

            GL.glUniformMatrix4fv(GL.glGetUniformLocation(self._shader_program, "u_mvp"), 1, GL_FALSE, mvp.data())
            GL.glUniformMatrix4fv(GL.glGetUniformLocation(self._shader_program, "u_model_view"), 1, GL_FALSE,
                                  model_view_matrix.data())

            # --- ИЗМЕНЕНИЕ: Биндим VBO ---
            GL.glEnableVertexAttribArray(0)  # aPos
            GL.glBindBuffer(GL_ARRAY_BUFFER, self._vbo_pos)
            GL.glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, 0, None)

            GL.glEnableVertexAttribArray(1)  # aNormalOrPos (HACK)
            GL.glBindBuffer(GL_ARRAY_BUFFER, self._vbo_pos)  # <-- Подаем тот же VBO, что и для aPos
            GL.glVertexAttribPointer(1, 3, GL_FLOAT, GL_FALSE, 0, None)

            GL.glEnableVertexAttribArray(2)  # aColor
            GL.glBindBuffer(GL_ARRAY_BUFFER, self._vbo_col)
            GL.glVertexAttribPointer(2, 3, GL_FLOAT, GL_FALSE, 0, None)
            # --- КОНЕЦ ИЗМЕНЕНИЙ ---

            # (Код отрисовки без изменений)
            GL.glUniform1i(GL.glGetUniformLocation(self._shader_program, "u_is_line"), 0)
            GL.glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, self._ibo_fill)
            GL.glDrawElements(GL_TRIANGLES, self._fill_indices.size, GL_UNSIGNED_INT, None)

            if self._render_settings.show_hex_grid:
                GL.glUniform1i(GL.glGetUniformLocation(self._shader_program, "u_is_line"), 1)
                GL.glLineWidth(1.0)
                GL.glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, self._ibo_lines)
                GL.glDrawElements(GL_LINES, self._line_indices.size, GL_UNSIGNED_INT, None)

            GL.glDisableVertexAttribArray(0)
            GL.glDisableVertexAttribArray(1)
            GL.glDisableVertexAttribArray(2)

        # --- 2. РИСУЕМ ПОЛЮСА (MVP теперь берется из камеры) ---
        if self._poles_shader_program:
            # (Код без изменений)
            GL.glUseProgram(self._poles_shader_program)
            GL.glUniformMatrix4fv(GL.glGetUniformLocation(self._poles_shader_program, "u_mvp"), 1, GL_FALSE, mvp.data())
            GL.glEnableVertexAttribArray(0)
            GL.glBindBuffer(GL_ARRAY_BUFFER, self._poles_vbo_pos)
            GL.glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, 0, None)
            GL.glEnableVertexAttribArray(1)
            GL.glBindBuffer(GL_ARRAY_BUFFER, self._poles_vbo_col)
            GL.glVertexAttribPointer(1, 3, GL_FLOAT, GL_FALSE, 0, None)
            GL.glDrawArrays(GL_POINTS, 0, 2)
            GL.glDisableVertexAttribArray(0)
            GL.glDisableVertexAttribArray(1)

    def resizeGL(self, w: int, h: int):
        GL.glViewport(0, 0, w, h)
        # --- ИЗМЕНЕНИЕ: Обновляем камеру ---
        self._camera.set_viewport(w, h)

    def mousePressEvent(self, event: QtGui.QMouseEvent):
        # --- ИЗМЕНЕНИЕ: Передаем управление камере ---
        self._camera.handle_mouse_press(event)

        # (Логика Ray-picking без изменений)
        if self._planet_data is None or 'centers_xyz' not in self._planet_data or self._vertices.size == 0:
            return
        average_radius = float(np.mean(np.linalg.norm(self._vertices, axis=1)))
        if average_radius < 0.1: average_radius = 1.0
        proj = self._camera.get_projection_matrix()
        view = self._camera.get_model_view_matrix()
        inv_view_proj, invertible = (proj * view).inverted()
        if not invertible:
            logger.warning("Матрица вида-проекции не обратима.")
            return
        x_ndc = (2.0 * event.position().x()) / self.width() - 1.0
        y_ndc = 1.0 - (2.0 * event.position().y()) / self.height()
        near_point_h = inv_view_proj.map(QtGui.QVector4D(x_ndc, y_ndc, -1.0, 1.0))
        far_point_h = inv_view_proj.map(QtGui.QVector4D(x_ndc, y_ndc, 1.0, 1.0))
        if near_point_h.w() == 0.0 or far_point_h.w() == 0.0:
            return
        ray_origin = near_point_h.toVector3D() / near_point_h.w()
        far_point = far_point_h.toVector3D() / far_point_h.w()
        ray_dir = (far_point - ray_origin).normalized()
        oc = ray_origin
        b = QtGui.QVector3D.dotProduct(oc, ray_dir)
        c = QtGui.QVector3D.dotProduct(oc, oc) - average_radius * average_radius
        discriminant = b * b - c
        if discriminant < 0:
            return
        intersection_dist = -b - math.sqrt(discriminant)
        intersection_point_3d = ray_origin + ray_dir * intersection_dist
        intersection_np = np.array([intersection_point_3d.x(), intersection_point_3d.y(), intersection_point_3d.z()],
                                   dtype=np.float32)
        intersection_np /= np.linalg.norm(intersection_np)
        closest_idx = nearest_cell_by_xyz(intersection_np, self._planet_data['centers_xyz'])
        self.cell_picked.emit(int(closest_idx))

    def mouseMoveEvent(self, event: QtGui.QMouseEvent):
        # --- ИЗМЕНЕНИЕ: Передаем управление камере ---
        if self._camera.handle_mouse_move(event):
            self.update()

    def wheelEvent(self, event: QtGui.QWheelEvent):
        # --- ИЗМЕНЕНИЕ: Передаем управление камере ---
        if self._camera.handle_wheel(event):
            self.update()