# Файл: game_engine_restructured/world/planners/water_planner.py
from __future__ import annotations
from typing import TYPE_CHECKING, Dict, Tuple, List
import numpy as np

if TYPE_CHECKING:
    from ...core.types import GenResult


def _stitch_layers(region_size: int, chunk_size: int, base_chunks: Dict[Tuple[int, int], GenResult],
                   layer_names: List[str]) -> Tuple[Dict[str, np.ndarray], Tuple[int, int]]:
    """Склеивает указанные слои из всех чанков региона в большие numpy-массивы."""
    region_pixel_size = region_size * chunk_size

    all_cx = [c[0] for c in base_chunks.keys()]
    all_cz = [c[1] for c in base_chunks.keys()]
    base_cx, base_cz = min(all_cx), min(all_cz)

    stitched_layers = {}
    for name in layer_names:
        # Определяем тип данных для массива
        is_object_array = name in ['surface', 'navigation']
        dtype = object if is_object_array else np.float32
        stitched_layers[name] = np.zeros((region_pixel_size, region_pixel_size), dtype=dtype)

    for (cx, cz), chunk_data in base_chunks.items():
        start_x = (cx - base_cx) * chunk_size
        start_y = (cz - base_cz) * chunk_size

        for name in layer_names:
            # Универсальный способ получить данные слоя (либо из 'layers', либо из 'height_q')
            source_data = chunk_data.layers.get(name)
            if name == 'height' and not source_data:
                source_data = chunk_data.layers.get("height_q", {}).get("grid")

            if source_data:
                grid = np.array(source_data)
                stitched_layers[name][start_y:start_y + chunk_size, start_x:start_x + chunk_size] = grid

    return stitched_layers, (base_cx, base_cz)


def _apply_changes_to_chunks(stitched_layers: Dict[str, np.ndarray], base_chunks: Dict[Tuple[int, int], GenResult],
                             base_cx: int, base_cz: int, chunk_size: int):
    """Нарезает измененные слои обратно в объекты чанков."""
    for (cx, cz), chunk in base_chunks.items():
        start_x = (cx - base_cx) * chunk_size
        start_y = (cz - base_cz) * chunk_size

        for name, grid in stitched_layers.items():
            sub_grid = grid[start_y:start_y + chunk_size, start_x:start_x + chunk_size]
            if name == 'height':
                chunk.layers["height_q"]["grid"] = sub_grid.tolist()
            else:
                chunk.layers[name] = sub_grid.tolist()