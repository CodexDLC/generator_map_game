# editor/render/core_gl/shader_library.py
"""
Хранилище GLSL-шейдеров.
"""

# --- ИЗМЕНЕНИЕ: Вершинный шейдер ---
VS_CODE = """
#version 330 core
layout (location = 0) in vec3 aPos;
// HACK: 
// Для сферы (u_is_sphere=true) сюда будет подан VBO вершин (aPos)
// Для региона (u_is_sphere=false) сюда будет подан VBO нормалей (aNormal)
layout (location = 1) in vec3 aNormalOrPos; 
layout (location = 2) in vec3 aColor;

uniform mat4 u_mvp;
uniform mat4 u_model_view;
uniform bool u_is_sphere; // <--- НОВЫЙ

out vec3 v_normal_view;
out vec3 v_pos_view;
out vec3 v_color;

void main() {
    gl_Position = u_mvp * vec4(aPos, 1.0);

    // --- НОВАЯ ЛОГИКА РАСЧЕТА НОРМАЛИ ---
    vec3 normal_model;
    if (u_is_sphere) {
        normal_model = normalize(aNormalOrPos); // aNormalOrPos == aPos
    } else {
        normal_model = aNormalOrPos;             // aNormalOrPos == aNormal
    }

    // Трансформируем нормаль в view-space
    v_normal_view = mat3(transpose(inverse(u_model_view))) * normal_model;
    v_pos_view = vec3(u_model_view * vec4(aPos, 1.0));
    v_color = aColor;
}
"""
# ------------------------------------

FS_CODE = """
#version 330 core
uniform int u_is_line;

// --- UNIFORMS ДЛЯ ОСВЕЩЕНИЯ ---
uniform vec3 u_light_dir_view; 
uniform float u_ambient;
uniform float u_diffuse;

in vec3 v_normal_view; 
in vec3 v_pos_view;    
in vec3 v_color;       

out vec4 FragColor;

void main() {
    if (u_is_line == 1) {
        FragColor = vec4(0.0, 0.0, 0.0, 1.0);
        return;
    }

    vec3 N = normalize(v_normal_view);
    vec3 L = normalize(-u_light_dir_view); 

    float diff_factor = max(dot(N, L), 0.0);

    vec3 base_color = clamp(v_color, 0.0, 1.0);
    vec3 final_color = base_color * (u_ambient + u_diffuse * diff_factor);

    FragColor = vec4(final_color, 1.0);
}
"""

# --- Шейдеры для маркеров полюсов (без изменений) ---
# ... (VS_POLES_CODE и FS_POLES_CODE остаются без изменений) ...
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