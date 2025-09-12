# Файл: game_engine_restructured/world/planners/water_planner.py
from __future__ import annotations
from typing import TYPE_CHECKING
import numpy as np
import random
import time

from ...core import constants as const
from ...algorithms.hydrology.fast_hydrology import (
    _build_d8_flow_directions, _flow_accumulation_from_dirs,
    _label_connected_components
)

if TYPE_CHECKING:
    from ...core.preset.model import Preset


def apply_sea_level(
        # ... (код этой функции остается без изменений) ...
        stitched_heights: np.ndarray,
        stitched_surface: np.ndarray,
        stitched_nav: np.ndarray,
        preset: Preset
):
    sea_level = preset.elevation.get("sea_level_m", 15.0)
    if sea_level is None: return
    print(f"  -> Applying sea level at {sea_level}m...")
    water_mask = stitched_heights <= sea_level
    rock_mask = stitched_surface == const.KIND_BASE_ROCK
    final_water_mask = water_mask & ~rock_mask
    stitched_surface[final_water_mask] = const.KIND_BASE_WATERBED
    stitched_nav[final_water_mask] = const.NAV_WATER


def generate_highland_lakes(
        # ... (код этой функции остается без изменений) ...
        stitched_heights: np.ndarray,
        stitched_surface: np.ndarray,
        stitched_nav: np.ndarray,
        stitched_humidity: np.ndarray | None,
        preset: Preset,
        seed: int
):
    water_cfg = preset.water
    if not water_cfg or not water_cfg.get("enabled", False):
        return
    print("  -> Searching for highland lakes (realistic pour point method)...")
    rng = random.Random(seed)
    sea_level = preset.elevation.get("sea_level_m", 15.0)
    from scipy.ndimage import label
    land_mask = stitched_heights > sea_level
    inverted_land = ~land_mask
    labeled_water, num_labels = label(inverted_land)
    edge_labels = np.unique(np.concatenate((labeled_water[0, :], labeled_water[-1, :],
                                            labeled_water[:, 0], labeled_water[:, -1])))
    lakes_created = 0
    for i in range(1, num_labels + 1):
        if i in edge_labels:
            continue
        basin_mask = labeled_water == i
        from scipy.ndimage import binary_dilation
        border_mask = binary_dilation(basin_mask) & ~basin_mask
        if not np.any(border_mask):
            continue
        border_heights = stitched_heights[border_mask]
        pour_point_height = np.min(border_heights)
        lake_mask = basin_mask & (stitched_heights < pour_point_height)
        if not np.any(lake_mask):
            continue
        if stitched_humidity is not None:
            avg_humidity = np.mean(stitched_humidity[lake_mask])
            base_chance = water_cfg.get("lake_chance_base", 0.1)
            hum_multiplier = water_cfg.get("lake_chance_humidity_multiplier", 3.0)
            final_chance = base_chance + (base_chance * avg_humidity * hum_multiplier)
            if rng.random() > final_chance:
                continue
        stitched_surface[lake_mask] = const.KIND_BASE_WATERBED
        stitched_nav[lake_mask] = const.NAV_WATER
        lakes_created += 1
    if lakes_created > 0:
        print(f"    -> Created {lakes_created} realistic highland lakes.")


def generate_rivers(
        stitched_heights_ext: np.ndarray,
        preset: Preset,
        chunk_size: int
) -> np.ndarray:
    """
    Генерирует маску рек, используя бинарный поиск для достижения целевого
    количества истоков в CORE-области.
    """
    river_cfg = preset.water.get("river", {})
    if not river_cfg or not river_cfg.get("enabled", False):
        return np.zeros_like(stitched_heights_ext, dtype=bool)

    print("  -> Generating rivers with binary search for target sources...")
    t0 = time.perf_counter()

    flow_dirs = _build_d8_flow_directions(stitched_heights_ext)
    flow_map = _flow_accumulation_from_dirs(stitched_heights_ext, flow_dirs)

    target_sources = river_cfg.get("target_sources_core", 3)

    # --- Бинарный поиск порога ---
    low_thr = 1.0
    high_thr = np.max(flow_map)
    best_mask = np.zeros_like(flow_map, dtype=bool)

    border_px = chunk_size

    for _ in range(river_cfg.get("binary_search_iters", 12)):
        mid_thr = (low_thr + high_thr) / 2.0
        if mid_thr <= low_thr: break

        potential_mask_ext = flow_map > mid_thr

        # --- Ключевой момент: считаем истоки только в CORE-области ---
        core_mask = potential_mask_ext[border_px:-border_px, border_px:-border_px]
        _, num_sources = _label_connected_components(core_mask)

        if num_sources < target_sources:
            high_thr = mid_thr  # Слишком мало рек, нужно снижать порог
        else:
            low_thr = mid_thr  # Слишком много рек, нужно повышать порог
            best_mask = potential_mask_ext

    # --- Фильтрация коротких рек ---
    final_labels, num_labels = _label_connected_components(best_mask)
    min_len = river_cfg.get("min_length_px", 128)

    for i in range(1, num_labels + 1):
        river_segment = final_labels == i
        if np.sum(river_segment) < min_len:
            best_mask[river_segment] = False

    t1 = time.perf_counter()
    final_core_mask = best_mask[border_px:-border_px, border_px:-border_px]
    _, final_sources = _label_connected_components(final_core_mask)

    print(
        f"    -> River network finalized in {(t1 - t0) * 1000:.1f} ms. Target sources: {target_sources}, Final: {final_sources}.")

    return best_mask