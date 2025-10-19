# editor/logic/preview_logic.py
from __future__ import annotations
import logging
import numpy as np
import json
from pathlib import Path

from NodeGraphQt import BaseNode

from editor.graph.graph_runner import run_graph
from editor.nodes.height.io.world_input_node import WorldInputNode

from generator_logic.terrain.global_sphere_noise import get_noise_for_region_preview

from typing import TYPE_CHECKING, Set, Tuple, Optional, Dict, Any

if TYPE_CHECKING:
    from editor.core.main_window import MainWindow
    from editor.nodes.base_node import GeneratorNode

logger = logging.getLogger(__name__)


def _get_target_node_and_mode(main_window: MainWindow) -> tuple[None, bool] | tuple[BaseNode, bool]:
    target_node = (main_window.graph.selected_nodes()[0]
                   if main_window.graph and main_window.graph.selected_nodes()
                   else main_window._last_selected_node)
    if not target_node:
        return None, False
    is_global_mode = _has_world_input_ancestor(target_node)
    return target_node, is_global_mode


def _prepare_context(main_window: MainWindow) -> Tuple[Dict[str, Any], int]:
    """
    Готовит контекст для генерации.
    Разрешение ВСЕГДА берется из настроек РЕГИОНА. Настройка превью ИГНОРИРУЕТСЯ.
    """
    context = main_window.project_manager.collect_ui_context(for_preview=False)
    try:
        # <<< НАЧАЛО ИЗМЕНЕНИЯ: Единственный источник разрешения - "Разрешение региона" >>>
        region_res_str = main_window.region_resolution_input.currentText()
        resolution = int(region_res_str.split('x')[0])
        # <<< КОНЕЦ ИЗМЕНЕНИЯ >>>
    except (AttributeError, ValueError, IndexError):
        resolution = 1024 # Фоллбэк

    vertex_distance = main_window.vertex_distance_input.value()
    world_side_m = resolution * vertex_distance
    context['WORLD_SIZE_METERS'] = world_side_m

    x_meters = np.linspace(-world_side_m / 2.0, world_side_m / 2.0, resolution, dtype=np.float32)
    z_meters = np.linspace(-world_side_m / 2.0, world_side_m / 2.0, resolution, dtype=np.float32)
    context['x_coords'], context['z_coords'] = np.meshgrid(x_meters, z_meters)
    return context, resolution


def _generate_world_input(main_window: "MainWindow", context: Dict[str, Any], sphere_params: dict,
                          return_coords_only: bool = False) -> np.ndarray:
    logger.info("Generating world input for region preview...")

    try:
        radius_text = main_window.planet_radius_label.text().replace(" км", "").replace(",", "").replace(" ", "")
        radius_m = float(radius_text) * 1000.0
        if radius_m < 1.0: raise ValueError("Radius is too small")
    except Exception:
        logger.warning("Could not parse radius from UI, falling back to default.")
        radius_m = 6371000.0

    x_m, z_m = context['x_coords'], context['z_coords']
    center_vec = np.array(main_window.current_world_offset, dtype=np.float32)
    center_vec /= np.linalg.norm(center_vec)
    up_vec = np.array([0.0, 1.0, 0.0], dtype=np.float32)
    if np.abs(np.dot(center_vec, up_vec)) > 0.99:
        up_vec = np.array([1.0, 0.0, 0.0], dtype=np.float32)
    tangent_u = np.cross(center_vec, up_vec)
    tangent_u /= np.linalg.norm(tangent_u)
    tangent_v = np.cross(center_vec, tangent_u)
    angular_x = x_m / radius_m
    angular_z = z_m / radius_m
    points_in_plane = (center_vec[np.newaxis, np.newaxis, :]
                       + tangent_u[np.newaxis, np.newaxis, :] * angular_x[..., np.newaxis]
                       + tangent_v[np.newaxis, np.newaxis, :] * angular_z[..., np.newaxis])
    coords_for_noise = points_in_plane / np.linalg.norm(points_in_plane, axis=-1, keepdims=True)
    coords_for_noise = coords_for_noise.astype(np.float32)

    if return_coords_only:
        return coords_for_noise

    logger.debug(f"Generated spherical coordinates for noise sampling, shape: {coords_for_noise.shape}")
    base_noise = get_noise_for_region_preview(
        sphere_params=sphere_params,
        coords_xyz=coords_for_noise
    )

    try:
        max_height_m = main_window.max_height_input.value()
        base_elevation_text = main_window.base_elevation_label.text().replace(" м", "").replace(",", "")
        base_elevation_m = float(base_elevation_text)
        amplitude_norm = base_elevation_m / max_height_m if max_height_m > 1e-6 else 1.0
    except Exception as e:
        logger.warning(f"Could not calculate amplitude norm: {e}, falling back to 1.0")
        amplitude_norm = 1.0

    final_noise = base_noise * amplitude_norm
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
    target_node, is_global_mode = _get_target_node_and_mode(main_window)
    if not target_node:
        return None

    # Теперь эта функция всегда использует "Разрешение региона"
    context, resolution = _prepare_context(main_window)

    if is_global_mode:
        continent_size_km = main_window.ws_continent_scale_km.value()
        frequency = 20000.0 / max(continent_size_km, 1.0)
        sphere_params = {
            'octaves': int(main_window.ws_octaves.value()),
            'gain': main_window.ws_gain.value(),
            'seed': main_window.ws_seed.value(),
            'frequency': frequency,
            'power': main_window.ws_power.value(),
        }
        base_noise = _generate_world_input(main_window, context, sphere_params)
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

    # Логика климата остается без изменений, она здесь не мешает
    biome_probabilities = {}
    if main_window.climate_enabled.isChecked():
        try:
            cache_path = Path(main_window.project_manager.current_project_path) / "cache" / "global_climate_data.json"
            if cache_path.exists():
                with open(cache_path, "r", encoding="utf-8") as f:
                    climate_data = json.load(f)
                region_id_str = str(main_window.current_region_id)
                region_climate = climate_data.get("region_data", {}).get(region_id_str)
                if region_climate:
                    biome_probabilities = region_climate.get("biome_probabilities", {})
        except Exception as e:
            logger.error(f"Ошибка при чтении кэша климата для превью: {e}")

    return {
        "final_map_01": final_map_01,
        "max_height": context.get('max_height_m', 1000.0),
        "vertex_distance": main_window.vertex_distance_input.value(),
        "north_vector_2d": None,
        "biome_probabilities": biome_probabilities
    }