# editor/render/sphere_preview_widget.py
from __future__ import annotations
import logging
import math

import numpy as np
from PySide6 import QtCore, QtGui
from PySide6.QtOpenGLWidgets import QOpenGLWidget
from OpenGL import GL
from OpenGL.GL import (
    GL_FRONT_AND_BACK, GL_LINE, GL_FILL, GL_POLYGON_OFFSET_FILL, GL_LINES,
    GL_COLOR_BUFFER_BIT, GL_DEPTH_BUFFER_BIT, GL_DEPTH_TEST, GL_TRIANGLES,
    GL_UNSIGNED_INT, GL_FLOAT, GL_FALSE, GL_ARRAY_BUFFER, GL_ELEMENT_ARRAY_BUFFER,
    GL_STATIC_DRAW, GL_VERTEX_SHADER, GL_FRAGMENT_SHADER
)

logger = logging.getLogger(__name__)

VS_CODE = """
#version 330 core
layout (location = 0) in vec3 aPos;
layout (location = 1) in float aHeight;
layout (location = 2) in vec3 aColor;

uniform mat4 mvp;

out vec3 v_normal;
out vec3 v_color;

void main()
{
    gl_Position = mvp * vec4(aPos, 1.0);
    v_normal = normalize(aPos);
    v_color = aColor;
}
"""

FS_CODE = """
#version 330 core
out vec4 FragColor;

in vec3 v_normal;
in vec3 v_color;

void main()
{
    vec3 lightDir = normalize(vec3(0.6, 0.4, 0.7));
    float diffuse = max(dot(v_normal, lightDir), 0.0);
    vec3 lighting = vec3(0.8) + vec3(0.2) * diffuse;
    vec3 final_color = v_color * lighting;
    FragColor = vec4(final_color, 1.0);
}
"""


class SpherePreviewWidget(QOpenGLWidget):
    cell_picked = QtCore.Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(512, 256)

        self._shader_program = None
        self._vbo = None
        self._height_vbo = None
        self._color_vbo = None
        self._ibo = None
        self._line_ibo = None

        self._vertices = np.array([], dtype=np.float32)
        self._heights = np.array([], dtype=np.float32)
        self._colors = np.array([], dtype=np.float32)
        self._indices = np.array([], dtype=np.uint32)
        self._line_indices = np.array([], dtype=np.uint32)

        self._planet_data = None

        self._cam_distance = 2.5
        self._rotation = QtGui.QQuaternion()
        self._last_mouse_pos = QtCore.QPoint()

        self._proj_matrix = QtGui.QMatrix4x4()
        self._view_matrix = QtGui.QMatrix4x4()

    def set_planet_data(self, data: dict):
        self._planet_data = data

    def get_planet_data(self) -> dict | None:
        return self._planet_data

    def set_geometry(self, vertices: np.ndarray, fill_indices: np.ndarray, line_indices: np.ndarray,
                     vertex_heights: np.ndarray, vertex_colors: np.ndarray):
        self.makeCurrent()
        if self._vbo is not None:
            GL.glDeleteBuffers(5, [self._vbo, self._height_vbo, self._color_vbo, self._ibo, self._line_ibo])
        self._vbo, self._height_vbo, self._color_vbo, self._ibo, self._line_ibo = None, None, None, None, None

        self._vertices = vertices if vertices is not None else np.array([], dtype=np.float32)
        self._heights = vertex_heights if vertex_heights is not None else np.array([], dtype=np.float32)
        self._colors = vertex_colors if vertex_colors is not None else np.array([], dtype=np.float32)
        self._indices = fill_indices if fill_indices is not None else np.array([], dtype=np.uint32)
        self._line_indices = line_indices if line_indices is not None else np.array([], dtype=np.uint32)

        self.doneCurrent()
        self.update()

    def initializeGL(self):
        logger.info("Initializing OpenGL for Sphere Widget...")
        vs = self.compile_shader(GL_VERTEX_SHADER, VS_CODE)
        fs = self.compile_shader(GL_FRAGMENT_SHADER, FS_CODE)
        self._shader_program = self.link_program(vs, fs)
        GL.glEnable(GL_DEPTH_TEST)
        GL.glClearColor(0.1, 0.1, 0.15, 1.0)

    def paintGL(self):
        GL.glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        if self._shader_program is None or self._vertices.size == 0: return

        if self._vbo is None:
            self._vbo = GL.glGenBuffers(1)
            GL.glBindBuffer(GL_ARRAY_BUFFER, self._vbo)
            GL.glBufferData(GL_ARRAY_BUFFER, self._vertices.nbytes, self._vertices, GL_STATIC_DRAW)
            # ... (остальной код создания буферов)
            self._height_vbo = GL.glGenBuffers(1)
            GL.glBindBuffer(GL_ARRAY_BUFFER, self._height_vbo)
            GL.glBufferData(GL_ARRAY_BUFFER, self._heights.nbytes, self._heights, GL_STATIC_DRAW)
            self._color_vbo = GL.glGenBuffers(1)
            GL.glBindBuffer(GL_ARRAY_BUFFER, self._color_vbo)
            GL.glBufferData(GL_ARRAY_BUFFER, self._colors.nbytes, self._colors, GL_STATIC_DRAW)
            self._ibo = GL.glGenBuffers(1)
            GL.glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, self._ibo)
            GL.glBufferData(GL_ELEMENT_ARRAY_BUFFER, self._indices.nbytes, self._indices, GL_STATIC_DRAW)
            self._line_ibo = GL.glGenBuffers(1)
            GL.glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, self._line_ibo)
            GL.glBufferData(GL_ELEMENT_ARRAY_BUFFER, self._line_indices.nbytes, self._line_indices, GL_STATIC_DRAW)

        GL.glUseProgram(self._shader_program)

        self._proj_matrix = QtGui.QMatrix4x4()
        self._proj_matrix.perspective(45.0, self.width() / max(1, self.height()), 0.1, 100.0)

        self._view_matrix = QtGui.QMatrix4x4()
        self._view_matrix.translate(0.0, 0.0, -self._cam_distance)
        self._view_matrix.rotate(self._rotation)

        mvp = self._proj_matrix * self._view_matrix
        GL.glUniformMatrix4fv(GL.glGetUniformLocation(self._shader_program, "mvp"), 1, GL_FALSE, mvp.data())

        GL.glEnableVertexAttribArray(0)
        GL.glBindBuffer(GL_ARRAY_BUFFER, self._vbo)
        GL.glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, 0, None)
        GL.glEnableVertexAttribArray(1)
        GL.glBindBuffer(GL_ARRAY_BUFFER, self._height_vbo)
        GL.glVertexAttribPointer(1, 1, GL_FLOAT, GL_FALSE, 0, None)
        GL.glEnableVertexAttribArray(2)
        GL.glBindBuffer(GL_ARRAY_BUFFER, self._color_vbo)
        GL.glVertexAttribPointer(2, 3, GL_FLOAT, GL_FALSE, 0, None)

        GL.glEnable(GL_POLYGON_OFFSET_FILL)
        GL.glPolygonOffset(1.0, 1.0)
        GL.glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, self._ibo)
        GL.glDrawElements(GL_TRIANGLES, self._indices.size, GL_UNSIGNED_INT, None)
        GL.glDisable(GL_POLYGON_OFFSET_FILL)

        GL.glLineWidth(2.0)
        GL.glDisableVertexAttribArray(2)
        GL.glVertexAttrib3f(2, 0.05, 0.05, 0.05)

        GL.glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, self._line_ibo)
        GL.glDrawElements(GL_LINES, self._line_indices.size, GL_UNSIGNED_INT, None)

        GL.glLineWidth(1.0)
        GL.glDisableVertexAttribArray(0)
        GL.glDisableVertexAttribArray(1)

    def resizeGL(self, w: int, h: int):
        GL.glViewport(0, 0, w, h)

    def mousePressEvent(self, event: QtGui.QMouseEvent):
        self._last_mouse_pos = event.position().toPoint()

        # --- НАЧАЛО НОВОЙ, ПРАВИЛЬНОЙ ЛОГИКИ PICKING (RAYCASTING) ---
        if self._planet_data is None or 'centers_xyz' not in self._planet_data:
            return

        centers_xyz = self._planet_data['centers_xyz']
        if centers_xyz is None or centers_xyz.shape[0] == 0:
            return

        # 1. Unproject: Преобразуем 2D клик мыши в 3D луч в мировых координатах
        pos = event.position()

        # Для unproject нужна Y-координата, инвертированная относительно окна
        win_y = self.height() - pos.y()

        viewport = QtCore.QRect(0, 0, self.width(), self.height())

        # Используем встроенную функцию unproject, она математически корректна
        near_world = QtGui.QVector3D(pos.x(), win_y, 0.0).unproject(self._view_matrix, self._proj_matrix, viewport)
        far_world = QtGui.QVector3D(pos.x(), win_y, 1.0).unproject(self._view_matrix, self._proj_matrix, viewport)

        # 2. Определяем начало и направление луча
        inverted_view, _ = self._view_matrix.inverted()
        ray_origin = inverted_view.map(QtGui.QVector3D(0, 0, 0))
        ray_direction = (far_world - near_world).normalized()

        # 3. Находим пересечение луча со сферой (радиус 1.0, центр в 0,0,0)
        oc = ray_origin
        b = 2.0 * QtGui.QVector3D.dotProduct(oc, ray_direction)
        c = QtGui.QVector3D.dotProduct(oc, oc) - 1.0
        discriminant = b * b - 4 * c

        if discriminant < 0:
            return  # Луч не пересекает сферу

        t = (-b - math.sqrt(discriminant)) / 2.0
        intersection_point_3d = ray_origin + t * ray_direction

        # 4. Находим ближайший центр гексагона к точке пересечения НА СФЕРЕ
        intersection_np = np.array([intersection_point_3d.x(), intersection_point_3d.y(), intersection_point_3d.z()],
                                   dtype=np.float32)
        distances_sq = np.sum((centers_xyz - intersection_np) ** 2, axis=1)
        closest_idx = np.argmin(distances_sq)

        # 5. Отправляем сигнал с правильным ID
        self.cell_picked.emit(int(closest_idx))
        # --- КОНЕЦ НОВОЙ ЛОГИКИ ---

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
        self._cam_distance = max(0.1, min(new_distance, 20.0))
        self.update()

    def compile_shader(self, shader_type, shader_source):
        shader = GL.glCreateShader(shader_type)
        GL.glShaderSource(shader, shader_source)
        GL.glCompileShader(shader)
        if not GL.glGetShaderiv(shader, GL.GL_COMPILE_STATUS):
            log = GL.glGetShaderInfoLog(shader).decode('utf-8')
            logger.error(f"Shader compilation failed: {log}")
            return None
        return shader

    def link_program(self, vs, fs):
        program = GL.glCreateProgram()
        GL.glAttachShader(program, vs)
        GL.glAttachShader(program, fs)
        GL.glLinkProgram(program)
        if not GL.glGetProgramiv(program, GL.GL_LINK_STATUS):
            log = GL.glGetProgramInfoLog(program).decode('utf-8')
            logger.error(f"Shader program linking failed: {log}")
            return None
        GL.glDeleteShader(vs);
        GL.glDeleteShader(fs)
        return program