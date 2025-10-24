# editor/render/core_gl/shader_manager.py
"""
Вспомогательные функции для компиляции и линковки шейдеров OpenGL.
(Код перенесен из editor/render/sphere_preview_widget.py)
"""
import logging
from OpenGL import GL
from OpenGL.GL import (
    GL_VERTEX_SHADER, GL_FRAGMENT_SHADER, GL_COMPILE_STATUS, GL_LINK_STATUS,
    glGetShaderiv, glGetShaderInfoLog, glCreateShader, glShaderSource,
    glCompileShader, glCreateProgram, glAttachShader, glLinkProgram,
    glGetProgramiv, glGetProgramInfoLog, glDeleteShader
)

logger = logging.getLogger(__name__)

def compile_shader(shader_type, shader_source: str):
    """
    Компилирует шейдер.
    (Перенесено из SpherePreviewWidget.compile_shader)
    """
    shader = glCreateShader(shader_type)
    glShaderSource(shader, shader_source)
    glCompileShader(shader)
    if not glGetShaderiv(shader, GL_COMPILE_STATUS):
        log = glGetShaderInfoLog(shader).decode('utf-8')
        logger.error(f"Shader compilation failed: {log}")
        return None
    return shader

def link_program(vs, fs):
    """
    Линкует вершинный и фрагментный шейдеры в программу.
    (Перенесено из SpherePreviewWidget.link_program)
    """
    program = glCreateProgram()
    glAttachShader(program, vs)
    glAttachShader(program, fs)
    glLinkProgram(program)
    if not glGetProgramiv(program, GL_LINK_STATUS):
        log = glGetProgramInfoLog(program).decode('utf-8')
        logger.error(f"Shader program linking failed: {log}")
        return None
    glDeleteShader(vs)
    glDeleteShader(fs)
    return program