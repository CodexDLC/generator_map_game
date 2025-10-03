# editor/logic/hex_map_logic.py
from __future__ import annotations
import logging
import math
from typing import Dict, Tuple, Optional
import numpy as np
from PySide6 import QtGui
from PIL import Image, ImageDraw
from PIL.ImageQt import ImageQt

from generator_logic.topology.icosa_grid import build_hexplanet
from generator_logic.topology.hex_mask import build_hex_mask
from generator_logic.terrain.global_sphere_noise import global_sphere_noise_wrapper

logger = logging.getLogger(__name__)


def build_planet_data(subdivision_level: int) -> dict:
    """
    Генерирует полную топологию планеты, включая соседей и 3D-координаты центров.
    """
    logger.info(f"Building planet data with subdivision level: {subdivision_level}")
    try:
        planet_data = build_hexplanet(f=subdivision_level)
        return {
            "neighbors": planet_data.get("neighbors", []),
            "pent_ids": planet_data.get("pent_ids", []),
            "cell_count": len(planet_data.get("centers_xyz", [])),
            "centers_xyz": planet_data.get("centers_xyz")
        }
    except Exception as e:
        logger.error(f"Failed to build planet data: {e}", exc_info=True)
        return {}


def unfold_planet_layout_correctly(planet_data: dict) -> Dict[int, Tuple[float, float]]:
    """
    Геометрически корректный "якорный" алгоритм раскладки на 2D-плоскости.
    """
    logger.info("Unfolding planet layout correctly using anchor method...")
    neighbors = planet_data.get("neighbors")
    centers_xyz = planet_data.get("centers_xyz")
    if neighbors is None or centers_xyz is None:
        return {}

    num_cells = len(neighbors)
    layout = {}
    parent_map = {i: -1 for i in range(num_cells)}

    queue = [0]
    visited = {0}
    layout[0] = (0.0, 0.0)

    hex_directions = [
        (1.0, 0.0), (0.5, -math.sqrt(3) / 2), (-0.5, -math.sqrt(3) / 2),
        (-1.0, 0.0), (-0.5, math.sqrt(3) / 2), (0.5, math.sqrt(3) / 2),
    ]

    head = 0
    while head < len(queue):
        current_id = queue[head]
        head += 1
        cx, cy = layout[current_id]

        c_xyz = centers_xyz[current_id]
        t_basis = np.array([1.0, 0.0, 0.0])
        if abs(np.dot(c_xyz, t_basis)) > 0.9: t_basis = np.array([0.0, 1.0, 0.0])
        t_vec = t_basis - c_xyz * np.dot(c_xyz, t_basis)
        t_vec /= np.linalg.norm(t_vec)
        b_vec = np.cross(c_xyz, t_vec)

        sorted_neighbors_with_angle = []
        for neighbor_id in neighbors[current_id]:
            n_xyz = centers_xyz[neighbor_id]
            v = n_xyz - c_xyz
            proj_x, proj_y = np.dot(v, t_vec), np.dot(v, b_vec)
            angle = math.atan2(proj_y, proj_x)
            sorted_neighbors_with_angle.append((angle, neighbor_id))
        sorted_neighbors_with_angle.sort()
        sorted_neighbor_ids = [nid for angle, nid in sorted_neighbors_with_angle]

        parent_id = parent_map.get(current_id, -1)
        anchor_2d_idx = -1
        anchor_sorted_idx = -1

        if parent_id != -1:
            parent_pos = layout[parent_id]
            vec_to_parent = (round(parent_pos[0] - cx, 3), round(parent_pos[1] - cy, 3))

            for i, d in enumerate(hex_directions):
                if abs(vec_to_parent[0] - d[0]) < 1e-3 and abs(vec_to_parent[1] - d[1]) < 1e-3:
                    anchor_2d_idx = i
                    break

            if parent_id in sorted_neighbor_ids:
                anchor_sorted_idx = sorted_neighbor_ids.index(parent_id)

        for i, neighbor_id in enumerate(sorted_neighbor_ids):
            if neighbor_id not in visited:
                direction_idx = i
                if anchor_2d_idx != -1:
                    offset = i - anchor_sorted_idx
                    direction_idx = (anchor_2d_idx + offset) % len(hex_directions)

                dx, dy = hex_directions[direction_idx]
                nx, ny = cx + dx, cy + dy

                layout[neighbor_id] = (nx, ny)
                visited.add(neighbor_id)
                queue.append(neighbor_id)
                parent_map[neighbor_id] = current_id

    return layout


def draw_unfolded_map(
        layout: Dict[int, Tuple[float, float]],
        planet_data: dict,
        sphere_params: dict,
        sea_level: float,
        subdivision_level: int,
        hex_size_px: int = 64,
) -> Optional[QtGui.QPixmap]:
    """
    Рисует карту-развертку, генерируя уникальный рельеф для каждого гекса
    с учетом его ориентации на сфере.
    """
    logger.info(f"Drawing seamless and oriented unfolded map...")
    if not layout: return None

    coords = np.array(list(layout.values()))
    min_x, max_x = np.min(coords[:, 0]), np.max(coords[:, 0])
    min_y, max_y = np.min(coords[:, 1]), np.max(coords[:, 1])
    padding = hex_size_px
    canvas_width = int((max_x - min_x + 2) * hex_size_px)
    canvas_height = int((max_y - min_y + 2) * (hex_size_px * math.sqrt(3) / 2))
    canvas = Image.new('RGB', (canvas_width, canvas_height), 'black')

    hex_mask_np = build_hex_mask(R=hex_size_px, m_px=0, feather_px=0, orientation="pointy")
    hex_mask_img = Image.fromarray((hex_mask_np * 255).astype(np.uint8), 'L')

    num_regions = 10 * subdivision_level**2 + 2
    hex_angular_size = 2.0 / math.sqrt(num_regions)
    u_coords = np.linspace(-0.5, 0.5, hex_size_px, dtype=np.float32) * hex_angular_size
    v_coords = np.linspace(-0.5, 0.5, hex_size_px, dtype=np.float32) * hex_angular_size
    u_grid, v_grid = np.meshgrid(u_coords, v_coords)

    neighbors = planet_data.get("neighbors")
    centers_xyz = planet_data.get("centers_xyz")

    for region_id, (hx, hy) in layout.items():
        center_xyz = centers_xyz[region_id]

        first_neighbor_id = neighbors[region_id][0]
        neighbor_xyz = centers_xyz[first_neighbor_id]
        vec_to_neighbor = neighbor_xyz - center_xyz
        proj_on_normal = center_xyz * np.dot(center_xyz, vec_to_neighbor)
        t_vec = vec_to_neighbor - proj_on_normal
        t_vec /= np.linalg.norm(t_vec)
        b_vec = np.cross(center_xyz, t_vec)

        coords_on_plane = center_xyz + u_grid[..., np.newaxis] * t_vec + v_grid[..., np.newaxis] * b_vec
        coords_on_sphere = coords_on_plane / np.linalg.norm(coords_on_plane, axis=-1, keepdims=True)

        context = {'project': {'seed': sphere_params.get('seed', 0)}}
        height_map_01 = global_sphere_noise_wrapper(context, sphere_params, coords_xyz=coords_on_sphere)

        if height_map_01 is None: continue

        land_color, sea_color = (80, 140, 60), (60, 90, 130)
        color_map = np.where(height_map_01[..., np.newaxis] > sea_level, land_color, sea_color).astype(np.uint8)
        region_img = Image.fromarray(color_map, 'RGB')
        region_img.putalpha(hex_mask_img)

        paste_x = int((hx - min_x) * hex_size_px + padding / 2)
        paste_y = int((hy - min_y) * (hex_size_px * math.sqrt(3) / 2) + padding / 2)
        canvas.paste(region_img, (paste_x, paste_y), region_img)

    q_img = ImageQt(canvas)
    return QtGui.QPixmap.fromImage(q_img)