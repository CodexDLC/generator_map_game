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

logger = logging.getLogger(__name__)

# --- НАЧАЛО ИЗМЕНЕНИЙ: Обновленные шейдеры с расчетом освещения ---
VS_CODE = """
#version 330 core
layout (location = 0) in vec3 aPos;
layout (location = 2) in vec3 aColor;

uniform mat4 u_mvp;
uniform mat4 u_model_view;

out vec3 v_normal_view;
out vec3 v_pos_view;
out vec3 v_color;

void main() {
    gl_Position = u_mvp * vec4(aPos, 1.0);

    // Нормаль для сферы - это просто нормализованная позиция вершины
    v_normal_view = mat3(transpose(inverse(u_model_view))) * normalize(aPos);
    v_pos_view = vec3(u_model_view * vec4(aPos, 1.0));
    v_color = aColor;
}
"""

FS_CODE = """
#version 330 core
out vec4 FragColor;

in vec3 v_normal_view;
in vec3 v_pos_view;
in vec3 v_color;

uniform vec3 u_light_dir_view;
uniform float u_ambient;
uniform float u_diffuse;
uniform bool u_is_line;

void main()
{
        if (u_is_line) {
            // ФИКС: Серые линии для контраста на heightmap (не белые/красные, не чёрные на тьме)
            FragColor = vec4(0.0, 1.0, 0.5, 1.0);
        }else {
        // Расчет простого диффузного освещения (модель Ламберта)
        vec3 normal = normalize(v_normal_view);
        float diff = max(dot(normal, normalize(u_light_dir_view)), 0.0);

        // Смешиваем основной цвет с интенсивностью света
        vec3 final_color = v_color * (u_ambient + u_diffuse * diff);
        FragColor = vec4(final_color, 1.0);
    }
}
"""


# --- КОНЕЦ ИЗМЕНЕНИЙ ---


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
        self._cam_distance = 2.5
        self._rotation = QtGui.QQuaternion()
        self._last_mouse_pos = QtCore.QPoint()
        self._render_settings = RenderSettings()

    def set_render_settings(self, settings: RenderSettings):
        self._render_settings = settings
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
        self.doneCurrent()
        self.update()

    def initializeGL(self):
        vs = self.compile_shader(GL_VERTEX_SHADER, VS_CODE)
        fs = self.compile_shader(GL_FRAGMENT_SHADER, FS_CODE)
        self._shader_program = self.link_program(vs, fs)

        GL.glEnable(GL_DEPTH_TEST)
        GL.glEnable(GL_CULL_FACE)
        GL.glEnable(GL_POLYGON_OFFSET_FILL)
        GL.glPolygonOffset(1.0, 1.0)

        GL.glClearColor(0.1, 0.1, 0.15, 1.0)

    # --- НАЧАЛО ИЗМЕНЕНИЙ: Обновленная функция отрисовки ---
    def paintGL(self):
        GL.glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        if self._shader_program is None or self._vertices.size == 0: return

        if self._vbo_pos is None:
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
        proj = QtGui.QMatrix4x4()
        proj.perspective(45.0, self.width() / max(1, self.height()), 0.1, 100.0)
        view = QtGui.QMatrix4x4()
        view.translate(0.0, 0.0, -self._cam_distance)
        view.rotate(self._rotation)
        mvp = proj * view

        GL.glUniformMatrix4fv(GL.glGetUniformLocation(self._shader_program, "u_mvp"), 1, GL_FALSE, mvp.data())
        GL.glUniformMatrix4fv(GL.glGetUniformLocation(self._shader_program, "u_model_view"), 1, GL_FALSE, view.data())

        s = self._render_settings
        az_rad = math.radians(s.light_azimuth_deg)
        alt_rad = math.radians(s.light_altitude_deg)
        # Направление источника света в мировых координатах
        light_dir_world = QtGui.QVector3D(
            math.cos(alt_rad) * math.sin(az_rad),
            math.cos(alt_rad) * math.cos(az_rad),
            math.sin(alt_rad)
        )
        # Преобразуем направление света в σύстему координат камеры
        light_dir_view = view.mapVector(light_dir_world).normalized()
        GL.glUniform3f(GL.glGetUniformLocation(self._shader_program, "u_light_dir_view"), light_dir_view.x(),
                       light_dir_view.y(), light_dir_view.z())
        GL.glUniform1f(GL.glGetUniformLocation(self._shader_program, "u_ambient"), s.ambient)
        GL.glUniform1f(GL.glGetUniformLocation(self._shader_program, "u_diffuse"), s.diffuse)

        GL.glEnableVertexAttribArray(0)
        GL.glBindBuffer(GL_ARRAY_BUFFER, self._vbo_pos)
        GL.glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, 0, None)
        GL.glEnableVertexAttribArray(2)
        GL.glBindBuffer(GL_ARRAY_BUFFER, self._vbo_col)
        GL.glVertexAttribPointer(2, 3, GL_FLOAT, GL_FALSE, 0, None)

        # 1. Рисуем заполненные полигоны
        GL.glUniform1i(GL.glGetUniformLocation(self._shader_program, "u_is_line"), 0)
        GL.glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, self._ibo_fill)
        GL.glDrawElements(GL_TRIANGLES, self._fill_indices.size, GL_UNSIGNED_INT, None)

        # 2. Рисуем линии гексов поверх
        GL.glUniform1i(GL.glGetUniformLocation(self._shader_program, "u_is_line"), 1)
        GL.glLineWidth(2.0)  # Толще — лучше видно на рельефе (было 1.0)
        GL.glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, self._ibo_lines)
        GL.glDrawElements(GL_LINES, self._line_indices.size, GL_UNSIGNED_INT, None)

        GL.glDisableVertexAttribArray(0)
        GL.glDisableVertexAttribArray(2)

    # --- КОНЕЦ ИЗМЕНЕНИЙ ---

    def resizeGL(self, w: int, h: int):
        GL.glViewport(0, 0, w, h)

    def mousePressEvent(self, event: QtGui.QMouseEvent):
        self._last_mouse_pos = event.position().toPoint()
        if self._planet_data is None or 'centers_xyz' not in self._planet_data: return
        centers_xyz = self._planet_data['centers_xyz']
        if centers_xyz is None or centers_xyz.shape[0] == 0: return
        proj = QtGui.QMatrix4x4()
        proj.perspective(45.0, self.width() / max(1, self.height()), 0.1, 100.0)
        view = QtGui.QMatrix4x4()
        view.translate(0.0, 0.0, -self._cam_distance)
        view.rotate(self._rotation)
        inv_proj, ok_proj = proj.inverted()
        inv_view, ok_view = view.inverted()
        if not (ok_proj and ok_view): return
        x = (2.0 * event.position().x()) / self.width() - 1.0
        y = 1.0 - (2.0 * event.position().y()) / self.height()
        ray_eye = inv_proj.map(QtGui.QVector4D(x, y, -1.0, 1.0))
        ray_eye = QtGui.QVector4D(ray_eye.x(), ray_eye.y(), -1.0, 0.0)
        ray_world = inv_view.map(ray_eye).toVector3D().normalized()
        camera_pos = inv_view.map(QtGui.QVector3D(0, 0, 0))
        oc = camera_pos - QtGui.QVector3D(0, 0, 0)
        b = QtGui.QVector3D.dotProduct(oc, ray_world)
        c = QtGui.QVector3D.dotProduct(oc, oc) - 1.0
        discriminant = b * b - c
        if discriminant < 0: return
        intersection_dist = -b - math.sqrt(discriminant)
        intersection_point = camera_pos + ray_world * intersection_dist
        intersection_np = np.array([intersection_point.x(), intersection_point.y(), intersection_point.z()],
                                   dtype=np.float32)
        distances_sq = np.sum((centers_xyz - intersection_np) ** 2, axis=1)
        closest_idx = np.argmin(distances_sq)
        self.cell_picked.emit(int(closest_idx))

    def mouseMoveEvent(self, event: QtGui.QMouseEvent):
        dx = event.position().toPoint().x() - self._last_mouse_pos.x()
        dy = event.position().toPoint().y() - self._last_mouse_pos.y()
        if event.buttons() & QtCore.Qt.MouseButton.LeftButton:
            axis = QtGui.QVector3D(dy, dx, 0.0).normalized()
            angle = math.sqrt(dx * dx + dy * dy) * 0.5
            self._rotation = QtGui.QQuaternion.fromAxisAndAngle(axis, angle) * self._rotation
            self.update()
        self._last_mouse_pos = event.position().toPoint()

    def wheelEvent(self, event: QtGui.QWheelEvent):
        new_distance = self._cam_distance - event.angleDelta().y() / 240.0
        self._cam_distance = max(1.1, min(new_distance, 10.0))
        self.update()

    def compile_shader(self, shader_type, shader_source):
        shader = GL.glCreateShader(shader_type)
        GL.glShaderSource(shader, shader_source)
        GL.glCompileShader(shader)
        if not GL.glGetShaderiv(shader, GL_COMPILE_STATUS):
            log = GL.glGetShaderInfoLog(shader).decode('utf-8')
            logger.error(f"Shader compilation failed: {log}")
            return None
        return shader

    def link_program(self, vs, fs):
        program = GL.glCreateProgram()
        GL.glAttachShader(program, vs)
        GL.glAttachShader(program, fs)
        GL.glLinkProgram(program)
        if not GL.glGetProgramiv(program, GL_LINK_STATUS):
            log = GL.glGetProgramInfoLog(program).decode('utf-8')
            logger.error(f"Shader program linking failed: {log}")
            return None
        GL.glDeleteShader(vs)
        GL.glDeleteShader(fs)
        return program