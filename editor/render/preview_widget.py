# editor/render/preview_widget.py
from __future__ import annotations
import gc
import logging
import numpy as np
from PySide6 import QtWidgets, QtCore, QtGui
from PySide6.QtOpenGLWidgets import QOpenGLWidget
from OpenGL import GL
from OpenGL.GL import *

from editor.core.render_settings import RenderSettings
# --- ИМПОРТЫ ДЛЯ НОВОГО РЕНДЕРА ---
from editor.render.core_gl import shader_library, shader_manager, lighting
from editor.render.core_gl.camera import TurntableCamera
from editor.render.region import region_mesh_builder

logger = logging.getLogger(__name__)


class Preview3DWidget(QOpenGLWidget):
    """
    Виджет 3D-превью РЕГИОНА.
    (Переписан с Vispy на QOpenGLWidget в Фазе 3).
    """

    def __init__(self, parent=None):
        # (Код __init__ без изменений)
        super().__init__(parent)
        self._settings = RenderSettings()
        self._shader_program = None
        self._vbo_pos, self._vbo_col, self._vbo_norm, self._ibo_fill = None, None, None, None
        self._fill_indices_count = 0
        self._camera = TurntableCamera(fov=self._settings.fov, distance=100.0, mode='z_up_turntable')

    def _clear_buffers(self):
        # (Код _clear_buffers без изменений)
        self.makeCurrent()
        if self._vbo_pos is not None:
            GL.glDeleteBuffers(4, [self._vbo_pos, self._vbo_col, self._vbo_norm, self._ibo_fill])
        self._vbo_pos, self._vbo_col, self._vbo_norm, self._ibo_fill = None, None, None, None
        self._fill_indices_count = 0
        self.doneCurrent()
        gc.collect()

    def apply_render_settings(self, s: RenderSettings) -> None:
        # (Код apply_render_settings без изменений)
        self._settings = s
        self._camera.set_fov(float(s.fov))
        self.update()

    def update_mesh(self, height_map: np.ndarray, cell_size: float, **kwargs) -> None:
        # (Код update_mesh без изменений)
        self._clear_buffers()
        if not isinstance(height_map, np.ndarray) or height_map.shape[0] < 2 or height_map.shape[1] < 2:
            return
        if not np.all(np.isfinite(height_map)):
            return
        s = self._settings
        z = np.ascontiguousarray(height_map * float(s.height_exaggeration), dtype=np.float32)

        # 1. Вызываем наш сборщик меша (теперь он вернет УПРОЩЕННЫЙ меш)
        mesh_data = region_mesh_builder._create_solid_mesh_data(z, cell_size, s)
        if not mesh_data:
            return

        vertices = mesh_data["vertices"]
        faces = mesh_data["faces"]
        colors = mesh_data["base_colors"]
        normals = mesh_data["normals"]

        self._fill_indices_count = faces.size

        # 2. Загружаем данные в VBO
        self.makeCurrent()
        self._vbo_pos = GL.glGenBuffers(1)
        GL.glBindBuffer(GL_ARRAY_BUFFER, self._vbo_pos)
        GL.glBufferData(GL_ARRAY_BUFFER, vertices.nbytes, vertices, GL_STATIC_DRAW)
        self._vbo_norm = GL.glGenBuffers(1)
        GL.glBindBuffer(GL_ARRAY_BUFFER, self._vbo_norm)
        GL.glBufferData(GL_ARRAY_BUFFER, normals.nbytes, normals, GL_STATIC_DRAW)
        self._vbo_col = GL.glGenBuffers(1)
        GL.glBindBuffer(GL_ARRAY_BUFFER, self._vbo_col)
        GL.glBufferData(GL_ARRAY_BUFFER, colors.nbytes, colors, GL_STATIC_DRAW)
        self._ibo_fill = GL.glGenBuffers(1)
        GL.glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, self._ibo_fill)
        GL.glBufferData(GL_ELEMENT_ARRAY_BUFFER, faces.nbytes, faces, GL_STATIC_DRAW)
        self.doneCurrent()

        # 3. Настраиваем камеру
        if s.auto_frame:
            h, w = height_map.shape
            zmin, zmax = float(np.nanmin(z)), float(np.nanmax(z))
            self._camera.set_range(
                x_range=(0, w * cell_size),
                y_range=(0, h * cell_size),
                z_range=(zmin, zmax)
            )
        self.update()

    def initializeGL(self):
        vs = shader_manager.compile_shader(GL_VERTEX_SHADER, shader_library.VS_CODE)
        fs = shader_manager.compile_shader(GL_FRAGMENT_SHADER, shader_library.FS_CODE)
        self._shader_program = shader_manager.link_program(vs, fs)
        if not self._shader_program:
            logger.error("Не удалось слинковать основную программу шейдеров!")
            return

        GL.glEnable(GL_DEPTH_TEST)
        # --- ИЗМЕНЕНИЕ: Отключаем отсечение ---
        # GL.glEnable(GL_CULL_FACE) # <--- ВЫКЛЮЧЕНО
        # ------------------------------------
        GL.glClearColor(0.0, 0.0, 0.0, 1.0)  # Черный фон

    def paintGL(self):
        # (Код paintGL без изменений)
        GL.glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        if not self._shader_program or self._fill_indices_count == 0:
            return
        camera_matrix = self._camera.get_camera_matrix()
        model_view_matrix = self._camera.get_model_view_matrix()
        proj_matrix = self._camera.get_projection_matrix()
        mvp = proj_matrix * model_view_matrix
        GL.glUseProgram(self._shader_program)
        s = self._settings
        light_dir_world = lighting.get_light_direction_from_angles(s.light_azimuth_deg, s.light_altitude_deg)
        ldw_vec3 = QtGui.QVector3D(light_dir_world[0], light_dir_world[1], light_dir_world[2])
        light_dir_view_vec4 = camera_matrix.map(QtGui.QVector4D(ldw_vec3, 0.0))
        light_dir_view = light_dir_view_vec4.toVector3D().normalized()
        GL.glUniform3f(GL.glGetUniformLocation(self._shader_program, "u_light_dir_view"), light_dir_view.x(),
                       light_dir_view.y(), light_dir_view.z())
        GL.glUniform1f(GL.glGetUniformLocation(self._shader_program, "u_ambient"), s.ambient)
        GL.glUniform1f(GL.glGetUniformLocation(self._shader_program, "u_diffuse"), s.diffuse)
        GL.glUniform1i(GL.glGetUniformLocation(self._shader_program, "u_is_sphere"), GL_FALSE)
        GL.glUniformMatrix4fv(GL.glGetUniformLocation(self._shader_program, "u_mvp"), 1, GL_FALSE, mvp.data())
        GL.glUniformMatrix4fv(GL.glGetUniformLocation(self._shader_program, "u_model_view"), 1, GL_FALSE,
                              model_view_matrix.data())
        GL.glEnableVertexAttribArray(0)  # aPos
        GL.glBindBuffer(GL_ARRAY_BUFFER, self._vbo_pos)
        GL.glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, 0, None)
        GL.glEnableVertexAttribArray(1)  # aNormalOrPos
        GL.glBindBuffer(GL_ARRAY_BUFFER, self._vbo_norm)
        GL.glVertexAttribPointer(1, 3, GL_FLOAT, GL_FALSE, 0, None)
        GL.glEnableVertexAttribArray(2)  # aColor
        GL.glBindBuffer(GL_ARRAY_BUFFER, self._vbo_col)
        GL.glVertexAttribPointer(2, 3, GL_FLOAT, GL_FALSE, 0, None)
        GL.glUniform1i(GL.glGetUniformLocation(self._shader_program, "u_is_line"), 0)
        GL.glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, self._ibo_fill)
        GL.glDrawElements(GL_TRIANGLES, self._fill_indices_count, GL_UNSIGNED_INT, None)
        GL.glDisableVertexAttribArray(0)
        GL.glDisableVertexAttribArray(1)
        GL.glDisableVertexAttribArray(2)

    def resizeGL(self, w: int, h: int):
        # (Код resizeGL без изменений)
        GL.glViewport(0, 0, w, h)
        self._camera.set_viewport(w, h)

    def mousePressEvent(self, event: QtGui.QMouseEvent):
        # (Код mousePressEvent без изменений)
        self._camera.handle_mouse_press(event)

    def mouseMoveEvent(self, event: QtGui.QMouseEvent):
        # (Код mouseMoveEvent без изменений)
        if self._camera.handle_mouse_move(event):
            self.update()

    def wheelEvent(self, event: QtGui.QWheelEvent):
        # (Код wheelEvent без изменений)
        if self._camera.handle_wheel(event):
            self.update()

    def closeEvent(self, e):
        # (Код closeEvent без изменений)
        self._clear_buffers()
        super().closeEvent(e)