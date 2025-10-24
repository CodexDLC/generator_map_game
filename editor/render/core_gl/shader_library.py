# editor/render/core_gl/shader_library.py
"""
Хранилище GLSL-шейдеров.
(Код перенесен из editor/render/sphere_preview_widget.py)
"""

# --- Шейдеры для основного рельефа ---
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
    v_normal_view = mat3(transpose(inverse(u_model_view))) * normalize(aPos);
    v_pos_view = vec3(u_model_view * vec4(aPos, 1.0));
    v_color = aColor;
}
"""

FS_CODE = """
#version 330 core
uniform int u_is_line;
in vec3 v_color;
out vec4 FragColor;

void main() {
    if (u_is_line == 1) {
        FragColor = vec4(0.0, 0.0, 0.0, 1.0);
        return;
    }
    vec3 base = clamp(v_color, 0.0, 1.0);
    FragColor = vec4(base, 1.0);
}
"""

# --- Шейдеры для маркеров полюсов ---
VS_POLES_CODE = """
#version 330 core
layout (location = 0) in vec3 aPos;
layout (location = 1) in vec3 aColor;

uniform mat4 u_mvp;
out vec3 v_color;

void main() {
    gl_Position = u_mvp * vec4(aPos, 1.0);
    v_color = aColor;
    gl_PointSize = 12.0;
}
"""

FS_POLES_CODE = """
#version 330 core
in vec3 v_color;
out vec4 FragColor;

void main() {
    FragColor = vec4(v_color, 1.0);
}
"""