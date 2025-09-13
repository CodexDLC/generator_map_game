# ==============================================================================
# Файл: game_engine_restructured/world/planners/water_planner.py
# Назначение: "Специалист" по созданию всех видов водных объектов.
# ==============================================================================
from __future__ import annotations
from typing import TYPE_CHECKING
import numpy as np
import random
import time

# --- Вспомогательные компоненты ---
from ...core import constants as const
from ...core.constants import KIND_BASE_WATERBED, NAV_WATER, surface_set, nav_set
from ...algorithms.hydrology.fast_hydrology import (
    _build_d8_flow_directions, _flow_accumulation_from_dirs,
    _label_connected_components
)
from scipy.ndimage import distance_transform_edt, label, binary_dilation

if TYPE_CHECKING:
    from ...core.preset.model import Preset


# ==============================================================================
# --- БЛОК 1: УРОВЕНЬ МОРЯ ---
# ==============================================================================

def apply_sea_level(height: np.ndarray, surface: np.ndarray, nav: np.ndarray, preset: "Preset") -> np.ndarray:
    """
    Создает моря и океаны, затопляя все участки ниже sea_level_m.
    - Изменяет текстуру поверхности на "дно" (waterbed).
    - Делает затопленные участки непроходимыми (water).
    """
    print(f"  -> Applying sea level...")
    sea_level = float(getattr(preset, "elevation", {}).get("sea_level_m", 40.0))

    # Создаем маску всех пикселей, которые находятся ниже уровня моря
    is_water_mask = (height < sea_level)

    # Применяем изменения по маске
    surface_set(surface, is_water_mask, KIND_BASE_WATERBED)
    nav_set(nav, is_water_mask, NAV_WATER)

    # Возвращаем маску для возможного дальнейшего использования
    return is_water_mask


# ==============================================================================
# --- КОНЕЦ БЛОКА 1 ---
# ==============================================================================


# ==============================================================================
# --- БЛОК 2: ВЫСОКОГОРНЫЕ ОЗЕРА ---
# ==============================================================================

def generate_highland_lakes(
        stitched_heights: np.ndarray,
        stitched_surface: np.ndarray,
        stitched_nav: np.ndarray,
        stitched_humidity: np.ndarray | None,
        preset: "Preset",
        seed: int
) -> None:
    """
    Находит замкнутые впадины в горах и, с некоторой вероятностью,
    заполняет их водой, создавая озера.
    """
    water_cfg = getattr(preset, "water", {})
    if not water_cfg.get("enabled", False):
        return

    print("  -> Searching for highland lakes...")
    rng = random.Random(seed)
    sea_level = getattr(preset, "elevation", {}).get("sea_level_m", 40.0)

    # Используем сложный алгоритм для поиска "чаш" на ландшафте
    land_mask = stitched_heights > sea_level
    inverted_mask = ~land_mask
    labeled_basins, num_basins = label(inverted_mask)

    # Исключаем впадины, которые соединены с краем карты (это заливы, а не озера)
    edge_labels = np.unique(np.concatenate((
        labeled_basins[0, :], labeled_basins[-1, :],
        labeled_basins[:, 0], labeled_basins[:, -1]
    )))

    lakes_created = 0
    for i in range(1, num_basins + 1):
        if i in edge_labels:
            continue

        basin_mask = (labeled_basins == i)
        border_mask = binary_dilation(basin_mask) & ~basin_mask
        if not np.any(border_mask):
            continue

        # Находим самую низкую точку на "краю" чаши - это уровень, до которого она заполнится
        pour_point_height = np.min(stitched_heights[border_mask])
        lake_mask = basin_mask & (stitched_heights < pour_point_height)
        if not np.any(lake_mask):
            continue

        # Учитываем влажность: в более влажных районах озера появляются чаще
        if stitched_humidity is not None:
            avg_humidity = float(np.mean(stitched_humidity[lake_mask]))
            base_chance = water_cfg.get("lake_chance_base", 0.10)
            multiplier = water_cfg.get("lake_chance_humidity_multiplier", 3.0)
            final_chance = base_chance + base_chance * avg_humidity * multiplier
            if rng.random() > final_chance:
                continue

        # Заполняем озеро водой
        surface_set(stitched_surface, lake_mask, KIND_BASE_WATERBED)
        nav_set(stitched_nav, lake_mask, NAV_WATER)
        lakes_created += 1

    if lakes_created > 0:
        print(f"    -> Created {lakes_created} realistic highland lakes.")


# ==============================================================================
# --- КОНЕЦ БЛОКА 2 ---
# ==============================================================================


# ==============================================================================
# --- БЛОК 3: РЕКИ ---
# ==============================================================================

def generate_rivers(
        stitched_heights_ext: np.ndarray,
        stitched_surface_ext: np.ndarray,
        stitched_nav_ext: np.ndarray,
        preset: "Preset",
        chunk_size: int
) -> np.ndarray:
    """
    Моделирует сток воды по ландшафту и в самых полноводных местах
    прорезает русла рек.
    """
    river_cfg = getattr(preset, "water", {}).get("river", {})
    if not river_cfg.get("enabled", False):
        return np.zeros_like(stitched_heights_ext, dtype=bool)

    print("  -> Generating rivers...")
    t0 = time.perf_counter()

    # Рассчитываем, куда потечет вода из каждой точки
    flow_dirs = _build_d8_flow_directions(stitched_heights_ext)
    # Рассчитываем, сколько "единиц" воды протекает через каждую точку
    flow_map = _flow_accumulation_from_dirs(stitched_heights_ext, flow_dirs)

    target_sources = int(river_cfg.get("target_sources_core", 3))

    # Подбираем такой порог "полноводности", чтобы получить нужное число рек
    low_thr, high_thr = 1.0, float(np.max(flow_map))
    best_mask = np.zeros_like(flow_map, dtype=bool)
    iters = int(river_cfg.get("binary_search_iters", 12))
    for _ in range(iters):
        mid_thr = (low_thr + high_thr) / 2.0
        if mid_thr <= low_thr or high_thr - low_thr < 1.0: break
        candidate_mask = flow_map > mid_thr
        core_mask = candidate_mask[chunk_size:-chunk_size, chunk_size:-chunk_size]
        num_sources = 0 if not np.any(core_mask) else _label_connected_components(core_mask)[1]
        if num_sources < target_sources:
            high_thr = mid_thr
        else:
            low_thr, best_mask = mid_thr, candidate_mask

    # Отфильтровываем слишком короткие ручейки
    labels, n = _label_connected_components(best_mask)
    min_len = int(river_cfg.get("min_length_px", 128))
    for i in range(1, n + 1):
        segment_mask = (labels == i)
        if int(np.sum(segment_mask)) < min_len:
            best_mask[segment_mask] = False

    # Прорезаем русло в земле и наносим текстуру воды
    if np.any(best_mask):
        river_dist = distance_transform_edt(~best_mask)
        W0, beta, Wmax = float(river_cfg.get("base_width_px", 1.5)), float(river_cfg.get("width_exponent", 0.6)), float(
            river_cfg.get("max_width_px", 10.0))
        normF = np.log(np.maximum(1.0, flow_map / (max(low_thr, 1.0) + 1e-6)))
        width = np.clip(W0 * normF ** beta, 0, Wmax)
        depth = np.clip(width * 0.4, 0.5, 5.0)
        carve_mask = (river_dist <= np.ceil(width)) & best_mask
        height_delta = depth * np.maximum(0.0, 1.0 - river_dist / (width + 1e-6))

        stitched_heights_ext[carve_mask] -= height_delta[carve_mask]
        surface_set(stitched_surface_ext, best_mask, const.KIND_BASE_WATERBED)
        nav_set(stitched_nav_ext, best_mask, const.NAV_WATER)

    t1 = time.perf_counter()
    print(f"    -> River network finalized in {(t1 - t0) * 1000:.1f} ms.")
    return best_mask

# ==============================================================================
# --- КОНЕЦ БЛОКА 3 ---
# ==============================================================================