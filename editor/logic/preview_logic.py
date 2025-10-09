# editor/logic/preview_logic.py
from __future__ import annotations
import logging
import traceback
import numpy as np
from PySide6 import QtWidgets
import cv2

from editor.graph.graph_runner import run_graph
from editor.nodes.height.io.world_input_node import WorldInputNode
from game_engine_restructured.world.planetary_grid import PlanetaryGrid
from generator_logic.terrain.global_sphere_noise import get_noise_for_region_preview

from typing import TYPE_CHECKING, Set, Tuple, Optional, Dict, Any

if TYPE_CHECKING:
    from editor.core.main_window import MainWindow
    from editor.nodes.base_node import GeneratorNode

logger = logging.getLogger(__name__)


def _get_target_node_and_mode(main_window: MainWindow) -> Tuple[Optional[GeneratorNode], bool]:
    target_node = (main_window.graph.selected_nodes()[0]
                   if main_window.graph and main_window.graph.selected_nodes()
                   else main_window._last_selected_node)
    if not target_node:
        return None, False
    is_global_mode = _has_world_input_ancestor(target_node)
    return target_node, is_global_mode


def _prepare_context(main_window: MainWindow) -> Tuple[Dict[str, Any], int]:
    context = main_window.project_manager.collect_ui_context(for_preview=False)
    try:
        region_res_str = main_window.region_resolution_input.currentText()
        resolution = int(region_res_str.split('x')[0])
    except (AttributeError, ValueError, IndexError):
        resolution = 4096

    vertex_distance = main_window.vertex_distance_input.value()
    world_side_m = resolution * vertex_distance
    context['WORLD_SIZE_METERS'] = world_side_m

    x_meters = np.linspace(-world_side_m / 2.0, world_side_m / 2.0, resolution, dtype=np.float32)
    z_meters = np.linspace(-world_side_m / 2.0, world_side_m / 2.0, resolution, dtype=np.float32)
    context['x_coords'], context['z_coords'] = np.meshgrid(x_meters, z_meters)
    return context, resolution


def _generate_world_input(main_window: MainWindow, resolution: int, sphere_params: dict) -> np.ndarray:
    try:
        max_height_m = main_window.max_height_input.value()
        base_elevation_text = main_window.base_elevation_label.text().replace(" м", "").replace(",", "")
        base_elevation_m = float(base_elevation_text)
        amplitude_norm = base_elevation_m / max_height_m if max_height_m > 1e-6 else 1.0
    except Exception:
        amplitude_norm = 1.0

    try:
        radius_text = main_window.planet_radius_label.text().replace(" км", "").replace(",", "").replace(" ", "")
        radius_m = float(radius_text) * 1000.0
        if radius_m < 1.0: raise ValueError("Radius is too small")
    except Exception:
        radius_m = 6371000.0

    planetary_grid = PlanetaryGrid(radius_m=radius_m)
    coords_for_noise = planetary_grid.get_coords_for_region(main_window.current_region_id, resolution) / radius_m

    base_noise = get_noise_for_region_preview(sphere_params=sphere_params, coords_xyz=coords_for_noise)

    # --- ИЗМЕНЕНИЕ: Убираем влияние уровня моря на геометрию ---
    final_noise = base_noise * amplitude_norm
    # --- КОНЕЦ ИЗМЕНЕНИЯ ---

    return final_noise.astype(np.float32)

def _has_world_input_ancestor(node: GeneratorNode, visited: Set[str] = None) -> bool:
    if visited is None: visited = set()
    if node.id in visited: return False
    visited.add(node.id)
    if isinstance(node, WorldInputNode): return True
    for port in node.inputs().values():
        for connected_port in port.connected_ports():
            if _has_world_input_ancestor(connected_port.node(), visited):
                return True
    return False


def generate_preview_data(main_window: MainWindow) -> Optional[Dict[str, Any]]:
    """
    Выполняет все вычисления и возвращает словарь с результатом для обновления UI.
    """
    target_node, is_global_mode = _get_target_node_and_mode(main_window)
    if not target_node:
        return None

    context, resolution = _prepare_context(main_window)

    if is_global_mode:
        logger.info("Сбор параметров глобального шума из UI для 3D-Превью...")

        # --- НАЧАЛО ИСПРАВЛЕНИЯ ---
        scale_value = main_window.ws_relative_scale.value()

        # Новая инвертированная формула, идентичная той, что в planet_view_logic
        min_freq, max_freq = 0.5, 10.0
        normalized_scale = (scale_value - 0.01) / 0.99
        frequency = max_freq - normalized_scale * (max_freq - min_freq)
        # --- КОНЕЦ ИСПРАВЛЕНИЯ ---

        sphere_params = {
            'octaves': int(main_window.ws_octaves.value()),
            'gain': main_window.ws_gain.value(),
            'seed': main_window.ws_seed.value(),
            'frequency': frequency,
            'power': main_window.ws_power.value(),
            'sea_level_pct': main_window.ws_sea_level.value(),
        }

        base_noise = _generate_world_input(main_window, resolution, sphere_params)
    else:
        base_noise = np.zeros_like(context['x_coords'], dtype=np.float32)

    context["world_input_noise"] = base_noise

    if np.any(base_noise) and main_window.graph:
        max_h = context.get('max_height_m', 1.0)
        stats = {
            'min_norm': np.min(base_noise), 'max_norm': np.max(base_noise), 'mean_norm': np.mean(base_noise),
            'min_m': np.min(base_noise) * max_h, 'max_m': np.max(base_noise) * max_h,
            'mean_m': np.mean(base_noise) * max_h
        }
        for node in main_window.graph.all_nodes():
            if isinstance(node, WorldInputNode):
                node.output_stats = stats
                break

    final_map_01 = run_graph(target_node, context)

    return {
        "final_map_01": final_map_01,
        "max_height": context.get('max_height_m', 1000.0),
        "vertex_distance": main_window.vertex_distance_input.value()
    }