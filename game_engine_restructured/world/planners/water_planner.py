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
from ...core.constants import (
    KIND_BASE_WATERBED, NAV_WATER,
    surface_set, nav_set
)
from scipy.ndimage import distance_transform_edt, label, binary_dilation

if TYPE_CHECKING:
    from ...core.preset.model import Preset

# ---------------- sea level ----------------

def apply_sea_level(height: np.ndarray,
                    surface: np.ndarray,
                    nav: np.ndarray,
                    preset) -> np.ndarray:
    sea = float(getattr(preset, "elevation", {}).get("sea_level_m", 40.0))
    is_water = (height < sea)
    surface_set(surface, is_water, KIND_BASE_WATERBED)
    nav_set(nav,       is_water, NAV_WATER)
    return is_water

# ---------------- lakes ----------------

def generate_highland_lakes(stitched_heights: np.ndarray,
                            stitched_surface: np.ndarray,
                            stitched_nav: np.ndarray,
                            stitched_humidity: np.ndarray | None,
                            preset: "Preset",
                            seed: int) -> None:
    water_cfg = getattr(preset, "water", {})
    if not water_cfg or not water_cfg.get("enabled", False):
        return
    print("  -> Searching for highland lakes (realistic pour point method)...")

    rng = random.Random(seed)
    sea_level = getattr(preset, "elevation", {}).get("sea_level_m", 40.0)

    land_mask = stitched_heights > sea_level
    inverted  = ~land_mask
    labeled, num = label(inverted)

    edge_labels = np.unique(np.concatenate((labeled[0, :], labeled[-1, :], labeled[:, 0], labeled[:, -1])))

    lakes = 0
    for i in range(1, num + 1):
        if i in edge_labels:
            continue
        basin = (labeled == i)
        border = binary_dilation(basin) & ~basin
        if not np.any(border):
            continue
        pour_h = np.min(stitched_heights[border])
        lake_mask = basin & (stitched_heights < pour_h)
        if not np.any(lake_mask):
            continue

        if stitched_humidity is not None:
            avg_h = float(np.mean(stitched_humidity[lake_mask]))
            base  = water_cfg.get("lake_chance_base", 0.10)
            mult  = water_cfg.get("lake_chance_humidity_multiplier", 3.0)
            chance = base + base * avg_h * mult
            if rng.random() > chance:
                continue

        surface_set(stitched_surface, lake_mask, KIND_BASE_WATERBED)
        nav_set(    stitched_nav,     lake_mask, NAV_WATER)
        lakes += 1

    if lakes:
        print(f"    -> Created {lakes} realistic highland lakes.")

# ---------------- rivers ----------------

def generate_rivers(stitched_heights_ext: np.ndarray,
                    stitched_surface_ext: np.ndarray,
                    stitched_nav_ext: np.ndarray,
                    preset: "Preset",
                    chunk_size: int) -> np.ndarray:
    """
    Генерирует маску рек (EXT), делает бинарный поиск порога аккумуляции
    под целевое число истоков в CORE, вырезает русло переменной ширины.
    """
    river_cfg = getattr(preset, "water", {}).get("river", {})
    if not river_cfg or not river_cfg.get("enabled", False):
        return np.zeros_like(stitched_heights_ext, dtype=bool)

    print("  -> Generating rivers with binary search for target sources...")
    t0 = time.perf_counter()

    flow_dirs = _build_d8_flow_directions(stitched_heights_ext)
    flow_map  = _flow_accumulation_from_dirs(stitched_heights_ext, flow_dirs)

    target_sources = int(river_cfg.get("target_sources_core", 3))
    border_px      = int(chunk_size)

    # --- binary search over threshold ---
    low_thr  = 1.0
    high_thr = float(np.max(flow_map))
    best_mask = np.zeros_like(flow_map, dtype=bool)

    iters = int(river_cfg.get("binary_search_iters", 12))
    for _ in range(iters):
        mid_thr = (low_thr + high_thr) / 2.0
        if mid_thr <= low_thr or high_thr - low_thr < 1.0:
            break

        cand = flow_map > mid_thr
        core = cand[border_px:-border_px, border_px:-border_px]
        num_sources = 0 if not np.any(core) else _label_connected_components(core)[1]

        if num_sources < target_sources:
            high_thr = mid_thr
        else:
            low_thr  = mid_thr
            best_mask = cand

    # --- фильтрация коротких ---
    labels, n = _label_connected_components(best_mask)
    min_len = int(river_cfg.get("min_length_px", 128))
    for i in range(1, n + 1):
        seg = (labels == i)
        if int(np.sum(seg)) < min_len:
            best_mask[seg] = False

    # --- вырезаем русло ---
    if np.any(best_mask):
        river_dist = distance_transform_edt(~best_mask)

        W0    = float(river_cfg.get("base_width_px", 1.5))
        beta  = float(river_cfg.get("width_exponent", 0.6))
        Wmax  = float(river_cfg.get("max_width_px", 10.0))

        thr   = max(low_thr, 1.0)
        normF = np.log(np.maximum(1.0, flow_map / (thr + 1e-6)))

        width = np.clip(W0 * normF ** beta, 0, Wmax)
        depth = np.clip(width * 0.4, 0.5, 5.0)

        carve_mask   = (river_dist <= np.ceil(width)) & best_mask
        height_delta = depth * np.maximum(0.0, 1.0 - river_dist / (width + 1e-6))

        stitched_heights_ext[carve_mask] -= height_delta[carve_mask]
        surface_set(stitched_surface_ext, best_mask, const.KIND_BASE_WATERBED)
        nav_set(    stitched_nav_ext,     best_mask, const.NAV_WATER)

    t1 = time.perf_counter()
    core_mask = best_mask[border_px:-border_px, border_px:-border_px]
    final_sources = 0 if not np.any(core_mask) else _label_connected_components(core_mask)[1]
    print(f"    -> River network finalized in {(t1 - t0) * 1000:.1f} ms. "
          f"Target sources: {target_sources}, Final: {final_sources}.")
    return best_mask
