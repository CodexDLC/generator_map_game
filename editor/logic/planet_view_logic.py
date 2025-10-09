# editor/logic/planet_view_logic.py
import logging
import math
import numpy as np
from PySide6 import QtWidgets
from pathlib import Path

# --- ИЗМЕНЕНИЕ: Добавлен недостающий импорт ---
from editor.render.planet_palettes import map_planet_palette_cpu
from generator_logic.topology.icosa_grid import build_hexplanet
from generator_logic.terrain.global_sphere_noise import get_noise_for_sphere_view
from editor.ui.layouts.world_settings_panel import PLANET_ROUGHNESS_PRESETS

logger = logging.getLogger(__name__)


# ... (вспомогательные функции _normalize_vector, _slerp, _subdivide_triangle остаются без изменений)
def _normalize_vector(v):
    norm = np.linalg.norm(v, axis=-1, keepdims=True)
    return v / np.maximum(norm, 1e-9)


def _slerp(u, v, t):
    u = u / max(np.linalg.norm(u), 1e-12)
    v = v / max(np.linalg.norm(v), 1e-12)
    dot = float(np.clip(np.dot(u, v), -1.0, 1.0))
    theta = math.acos(dot)
    if theta < 1e-6: return u.copy()
    sin_theta = math.sin(theta)
    a = math.sin((1.0 - t) * theta) / sin_theta
    b = math.sin(t * theta) / sin_theta
    w = a * u + b * v
    return w / max(np.linalg.norm(w), 1e-12)


def _subdivide_triangle(v1, v2, v3, level):
    if level <= 0: return [(v1, v2, v3)]
    m12, m23, m31 = _slerp(v1, v2, 0.5), _slerp(v2, v3, 0.5), _slerp(v3, v1, 0.5)
    tris = []
    tris.extend(_subdivide_triangle(v1, m12, m31, level - 1))
    tris.extend(_subdivide_triangle(m12, v2, m23, level - 1))
    tris.extend(_subdivide_triangle(m31, m23, v3, level - 1))
    tris.extend(_subdivide_triangle(m12, m23, m31, level - 1))
    return tris


def _generate_hex_sphere_geometry(planet_data, sphere_params, disp_scale, subdivision_level) -> tuple:
    polys_lonlat = planet_data['cell_polys_lonlat_rad']
    centers_xyz = planet_data['centers_xyz']

    def lonlat_to_xyz(lon, lat, radius=1.0):
        lon, lat = float(lon), float(lat)
        x = math.cos(lat) * math.cos(lon)
        y = math.cos(lat) * math.sin(lon)
        z = math.sin(lat)
        v = np.array([x, y, z], dtype=np.float64)
        return (_normalize_vector(v) * radius).astype(np.float32)

    all_triangles = []
    for i, poly in enumerate(polys_lonlat):
        if len(poly) < 3: continue
        poly_verts_3d = _normalize_vector(np.array([lonlat_to_xyz(lon, lat) for lon, lat in poly], dtype=np.float32))
        center_3d = _normalize_vector(centers_xyz[i].astype(np.float32))
        for j in range(len(poly_verts_3d)):
            v1, v2 = poly_verts_3d[j], poly_verts_3d[(j + 1) % len(poly_verts_3d)]
            all_triangles.extend(_subdivide_triangle(center_3d, v1, v2, subdivision_level))

    vertex_map, unique_vertices, final_triangles_indices = {}, [], []
    for tri in all_triangles:
        tri_idx = []
        for v in tri:
            key = tuple(np.round(v, 6))
            if key not in vertex_map:
                vertex_map[key] = len(unique_vertices)
                unique_vertices.append(np.asarray(v, dtype=np.float32))
            tri_idx.append(vertex_map[key])
        final_triangles_indices.append(tri_idx)

    V_sphere_base = _normalize_vector(np.array(unique_vertices, dtype=np.float32))
    F_fill = np.array(final_triangles_indices, dtype=np.uint32)

    heights_01 = get_noise_for_sphere_view(sphere_params, V_sphere_base).flatten()

    colors = map_planet_palette_cpu(heights_01, "Grayscale")
    displaced_vertices = V_sphere_base * (1.0 + disp_scale * (heights_01 - 0.5))[:, np.newaxis]

    I_lines, line_vertex_map, line_unique_vertices = [], {}, []
    for poly in polys_lonlat:
        poly_indices = []
        for lon, lat in poly:
            key = (round(lon, 6), round(lat, 6))
            if key not in line_vertex_map:
                line_vertex_map[key] = len(line_unique_vertices)
                line_unique_vertices.append(lonlat_to_xyz(lon, lat))
            poly_indices.append(line_vertex_map[key])
        for k in range(len(poly_indices)): I_lines.append([poly_indices[k], poly_indices[(k + 1) % len(poly_indices)]])

    r_fill_max = float(np.linalg.norm(displaced_vertices, axis=1).max())
    line_vertices_displaced = _normalize_vector(np.array(line_unique_vertices, dtype=np.float32)) * (
                r_fill_max + max(0.002, 0.01 * r_fill_max))

    offset = len(displaced_vertices)
    all_vertices = np.vstack([displaced_vertices, line_vertices_displaced]).astype(np.float32)
    all_colors = np.vstack([colors.reshape(-1, 3), np.zeros_like(line_vertices_displaced)])
    all_line_indices = (np.array(I_lines, dtype=np.uint32) + offset).flatten()

    return all_vertices, F_fill, all_line_indices, all_colors


def orchestrate_planet_update(main_window) -> dict:
    radius_text = main_window.planet_radius_label.text().replace(" км", "").replace(",", "").replace(" ", "")
    radius_km = float(radius_text) if radius_text and radius_text != 'Ошибка' else 1.0
    radius_m = radius_km * 1000.0
    if radius_m < 1.0: raise ValueError("Радиус планеты слишком мал")

    preset_name = main_window.planet_type_preset_input.currentText()
    roughness_pct, _ = PLANET_ROUGHNESS_PRESETS.get(preset_name, (0.003, 2.5))

    disp_scale = roughness_pct * 1.5

    scale_value = main_window.ws_relative_scale.value()
    min_freq, max_freq = 0.5, 10.0
    normalized_scale = (scale_value - 0.01) / 0.99
    frequency = max_freq - normalized_scale * (max_freq - min_freq)

    detail_text = main_window.planet_preview_detail_input.currentText()
    subdivision_level = int(detail_text.split("(")[1].replace(")", ""))
    subdivision_level_grid = int(main_window.subdivision_level_input.currentText().split(" ")[0])

    sphere_params = {
        'octaves': int(main_window.ws_octaves.value()),
        'gain': main_window.ws_gain.value(),
        'seed': main_window.ws_seed.value(),
        'frequency': frequency,
        'power': main_window.ws_power.value(),
    }

    planet_data = build_hexplanet(f=subdivision_level_grid)
    if not planet_data: raise RuntimeError("Failed to generate planet data.")

    V, F_fill, I_lines, C = _generate_hex_sphere_geometry(
        planet_data, sphere_params, disp_scale, subdivision_level
    )

    if main_window.project_manager.current_project_path:
        cache_dir = Path(main_window.project_manager.current_project_path) / "cache"
        cache_dir.mkdir(exist_ok=True)
        cache_file = cache_dir / "planet_geometry.npz"
        np.savez_compressed(cache_file, vertices=V, fill_indices=F_fill, line_indices=I_lines, colors=C,
                            planet_data=planet_data)
        logger.info(f"Геометрия планеты сохранена в кэш: {cache_file}")

    return {
        "vertices": V, "fill_indices": F_fill, "line_indices": I_lines,
        "colors": C, "planet_data": planet_data
    }