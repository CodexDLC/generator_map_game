# editor/render/sphere_preview_widget.py
from __future__ import annotations
import logging
import math

import numpy as np
from PySide6 import QtCore, QtGui
from PySide6.QtOpenGLWidgets import QOpenGLWidget
from OpenGL import GL

logger = logging.getLogger(__name__)

VS_CODE = """
#version 330 core
layout (location = 0) in vec3 aPos;

uniform mat4 mvp;
uniform sampler2D heightTex;
uniform float disp_scale;
uniform float lon0_rad;

out vec2 v_uv;

vec2 uv_from_xyz(vec3 p) {
  float lon = atan(p.y, p.x) - lon0_rad;
  lon = lon / (2.0 * 3.14159265) + 0.5;
  float lat = asin(clamp(p.z, -1.0, 1.0));
  float v = (lat / 3.14159265) + 0.5;
  return vec2(lon, v);
}

void main()
{
    v_uv = uv_from_xyz(aPos);
    float h = texture(heightTex, v_uv).r;
    vec3 displaced = normalize(aPos) * (1.0 + disp_scale * (h - 0.5));
    gl_Position = mvp * vec4(displaced, 1.0);
}
"""

FS_CODE = """
#version 330 core
out vec4 FragColor;

in vec2 v_uv;

uniform sampler2D edgeTex;
uniform vec3 colorLand;
uniform vec3 colorLines;

void main()
{
    float edge = texture(edgeTex, v_uv).r;
    vec3 base_color = colorLand; // Simplified, no lighting for now
    vec3 final_color = mix(base_color, colorLines, edge);
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
        self._ibo = None
        self._height_tex = None
        self._edge_tex = None
        
        self._vertices = np.array([], dtype=np.float32)
        self._indices = np.array([], dtype=np.uint32)
        self._centers_xyz = np.array([], dtype=np.float32)
        
        self._cam_distance = 2.5
        self._rotation = QtGui.QQuaternion()
        self._last_mouse_pos = QtCore.QPoint()
        self._disp_scale = 0.1
        self._lon0_rad = 0.0

    def set_geometry(self, vertices: np.ndarray, indices: np.ndarray):
        self.makeCurrent()
        if self._vbo is not None: GL.glDeleteBuffers(1, [self._vbo])
        if self._ibo is not None: GL.glDeleteBuffers(1, [self._ibo])
        self._vbo, self._ibo = None, None
        self._vertices = vertices.astype(np.float32)
        self._indices = indices.astype(np.uint32)
        self.doneCurrent()
        self.update()

    def set_textures(self, height_qimage: QtGui.QImage, edge_qimage: QtGui.QImage):
        self.makeCurrent()
        if self._height_tex is not None: GL.glDeleteTextures(1, [self._height_tex])
        if self._edge_tex is not None: GL.glDeleteTextures(1, [self._edge_tex])
        self._height_tex = self._create_texture_from_qimage(height_qimage)
        self._edge_tex = self._create_texture_from_qimage(edge_qimage)
        self.doneCurrent()
        self.update()

    def set_centers(self, centers_xyz: np.ndarray):
        self._centers_xyz = centers_xyz.astype(np.float32)

    def set_disp_scale(self, scale: float):
        self._disp_scale = scale
        self.update()

    def set_lon0_rad(self, lon0_rad: float):
        self._lon0_rad = lon0_rad
        self.update()

    def initializeGL(self):
        logger.info("Initializing OpenGL...")
        vs = self.compile_shader(GL.GL_VERTEX_SHADER, VS_CODE)
        fs = self.compile_shader(GL.GL_FRAGMENT_SHADER, FS_CODE)
        self._shader_program = self.link_program(vs, fs)
        GL.glEnable(GL.GL_DEPTH_TEST)
        GL.glClearColor(0.1, 0.1, 0.15, 1.0)

    def paintGL(self):
        GL.glClear(GL.GL_COLOR_BUFFER_BIT | GL.GL_DEPTH_BUFFER_BIT)
        if self._shader_program is None or self._vertices.size == 0: return

        if self._vbo is None:
            self._vbo = GL.glGenBuffers(1)
            self._ibo = GL.glGenBuffers(1)
            GL.glBindBuffer(GL.GL_ARRAY_BUFFER, self._vbo)
            GL.glBufferData(GL.GL_ARRAY_BUFFER, self._vertices.nbytes, self._vertices, GL.GL_STATIC_DRAW)
            GL.glBindBuffer(GL.GL_ELEMENT_ARRAY_BUFFER, self._ibo)
            GL.glBufferData(GL.GL_ELEMENT_ARRAY_BUFFER, self._indices.nbytes, self._indices, GL.GL_STATIC_DRAW)

        GL.glUseProgram(self._shader_program)
        
        proj = QtGui.QMatrix4x4(); proj.perspective(45.0, self.width() / max(1, self.height()), 0.1, 100.0)
        view = QtGui.QMatrix4x4(); view.translate(0.0, 0.0, -self._cam_distance); view.rotate(self._rotation)
        mvp = proj * view * QtGui.QMatrix4x4()
        GL.glUniformMatrix4fv(GL.glGetUniformLocation(self._shader_program, "mvp"), 1, GL.GL_FALSE, mvp.data())
        GL.glUniform1f(GL.glGetUniformLocation(self._shader_program, "disp_scale"), self._disp_scale)
        GL.glUniform1f(GL.glGetUniformLocation(self._shader_program, "lon0_rad"), self._lon0_rad)
        GL.glUniform3f(GL.glGetUniformLocation(self._shader_program, "colorLand"), 0.4, 0.6, 0.3)
        GL.glUniform3f(GL.glGetUniformLocation(self._shader_program, "colorLines"), 0.9, 0.9, 0.9)

        GL.glActiveTexture(GL.GL_TEXTURE0)
        GL.glBindTexture(GL.GL_TEXTURE_2D, self._height_tex or 0)
        GL.glUniform1i(GL.glGetUniformLocation(self._shader_program, "heightTex"), 0)

        GL.glActiveTexture(GL.GL_TEXTURE1)
        GL.glBindTexture(GL.GL_TEXTURE_2D, self._edge_tex or 0)
        GL.glUniform1i(GL.glGetUniformLocation(self._shader_program, "edgeTex"), 1)

        GL.glBindBuffer(GL.GL_ARRAY_BUFFER, self._vbo)
        pos_loc = GL.glGetAttribLocation(self._shader_program, "aPos")
        GL.glVertexAttribPointer(pos_loc, 3, GL.GL_FLOAT, GL.GL_FALSE, 0, None)
        GL.glEnableVertexAttribArray(pos_loc)
        
        GL.glBindBuffer(GL.GL_ELEMENT_ARRAY_BUFFER, self._ibo)
        GL.glDrawElements(GL.GL_TRIANGLES, self._indices.size, GL.GL_UNSIGNED_INT, None)
        
        GL.glDisableVertexAttribArray(pos_loc)

    def resizeGL(self, w: int, h: int): GL.glViewport(0, 0, w, h)

    def mousePressEvent(self, event: QtGui.QMouseEvent):
        self._last_mouse_pos = event.position().toPoint()
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            self._pick_cell(event.position().toPoint())

    def mouseMoveEvent(self, event: QtGui.QMouseEvent):
        dx = event.position().toPoint().x() - self._last_mouse_pos.x()
        dy = event.position().toPoint().y() - self._last_mouse_pos.y()
        if event.buttons() & QtCore.Qt.MouseButton.RightButton:
            axis = QtGui.QVector3D(dy, dx, 0.0).normalized()
            angle = math.sqrt(dx*dx + dy*dy) * 0.5
            self._rotation = QtGui.QQuaternion.fromAxisAndAngle(axis, angle) * self._rotation
            self.update()
        self._last_mouse_pos = event.position().toPoint()

    def wheelEvent(self, event: QtGui.QWheelEvent):
        self._cam_distance -= event.angleDelta().y() / 240.0
        self._cam_distance = max(1.1, min(self._cam_distance, 20.0))
        self.update()

    def _pick_cell(self, pos: QtCore.QPoint):
        if self._centers_xyz.size == 0: return
        
        x, y = pos.x(), self.height() - pos.y()
        
        # Unproject from screen to world
        proj = QtGui.QMatrix4x4(); proj.perspective(45.0, self.width() / max(1, self.height()), 0.1, 100.0)
        view = QtGui.QMatrix4x4(); view.translate(0.0, 0.0, -self._cam_distance); view.rotate(self._rotation)
        inv_vp = (proj * view).inverted()[0]
        
        ndc = QtGui.QVector4D(2.0 * x / self.width() - 1.0, 2.0 * y / self.height() - 1.0, -1.0, 1.0)
        ray_eye = inv_vp * ndc; ray_eye.setW(0)
        ray_world = ray_eye.normalized().toVector3D()

        # Ray-sphere intersection (sphere at origin, radius 1)
        # For camera at origin, ray starts at origin, so we just need direction
        p = ray_world

        # Find closest cell center
        dots = np.dot(self._centers_xyz, [p.x(), p.y(), p.z()])
        picked_id = int(np.argmax(dots))
        logger.info(f"Picked cell #{picked_id} in 3D view.")
        self.cell_picked.emit(picked_id)

    def _create_texture_from_qimage(self, qimage: QtGui.QImage) -> int:
        if qimage is None or qimage.isNull(): return 0
        qimage = qimage.convertToFormat(QtGui.QImage.Format.Format_RGBA8888)
        ptr = qimage.constBits()
        tex_id = GL.glGenTextures(1)
        GL.glBindTexture(GL.GL_TEXTURE_2D, tex_id)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_WRAP_S, GL.GL_REPEAT)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_WRAP_T, GL.GL_CLAMP_TO_EDGE)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MIN_FILTER, GL.GL_LINEAR)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MAG_FILTER, GL.GL_LINEAR)
        GL.glTexImage2D(GL.GL_TEXTURE_2D, 0, GL.GL_RGBA, qimage.width(), qimage.height(), 0, GL.GL_RGBA, GL.GL_UNSIGNED_BYTE, ptr)
        return tex_id

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
        GL.glDeleteShader(vs); GL.glDeleteShader(fs)
        return program
