# ==============================================================================
# Файл: game_engine_restructured/algorithms/hydrology.py
# Назначение: "Специалист" по созданию всех видов водных объектов: морей,
#             высокогорных озер и рек.
# ВЕРСИЯ 2.0: Исправлены импорты и логика фильтрации озер.
# ==============================================================================
from __future__ import annotations
from typing import TYPE_CHECKING
import numpy as np
import random
import time

# --- Вспомогательные компоненты ---
from ..core import constants as const
# Используем удобные функции-обертки для работы с ID
from ..core.constants import KIND_BASE_WATERBED, NAV_WATER, surface_set, nav_set
from ..numerics.fast_hydrology import (
    build_d8_flow_directions, flow_accumulation_from_dirs,
    label_connected_components
)
from scipy.ndimage import distance_transform_edt, label, binary_dilation

if TYPE_CHECKING:
    from ..core.preset import Preset


# ==============================================================================
# --- БЛОК 1: УРОВЕНЬ МОРЯ ---
# ==============================================================================

def apply_sea_level(height: np.ndarray, surface: np.ndarray, nav: np.ndarray, preset: "Preset") -> np.ndarray:
    """
    Создает моря и океаны, затопляя все участки ниже sea_level_m.
    - Изменяет текстуру поверхности на "дно" (waterbed).
    - Делает затопленные участки непроходимыми (water).
    """
    print("  -> [Hydrology] Применение уровня моря...")
    sea_level = float(getattr(preset, "elevation", {}).get("sea_level_m", 40.0))

    # Создаем маску всех пикселей, которые находятся ниже уровня моря
    is_water_mask = (height < sea_level)

    # Применяем изменения по маске
    surface_set(surface, is_water_mask, KIND_BASE_WATERBED)
    nav_set(nav, is_water_mask, NAV_WATER)

    # Возвращаем маску для возможного дальнейшего использования
    return is_water_mask

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

    print("  -> [Hydrology] Поиск высокогорных озер...")
    rng = random.Random(seed)
    sea_level = getattr(preset, "elevation", {}).get("sea_level_m", 40.0)

    # Ищем впадины только на суше (выше уровня моря)
    land_mask = stitched_heights >= sea_level
    labeled_basins, num_basins = label(land_mask == False) # Ищем "дырки" в суше

    if num_basins == 0:
        return

    # --- ИСПРАВЛЕНА ЛОГИКА: Корректная фильтрация мелких впадин ---
    min_lake_size = int(water_cfg.get("min_lake_size_px", 20))
    unique_labels, basin_sizes = np.unique(labeled_basins, return_counts=True)
    # Отбираем ID только тех "бассейнов", которые достаточно большие
    valid_labels = unique_labels[(basin_sizes >= min_lake_size) | (unique_labels == 0)] # 0 - это фон, его оставляем
    # Создаем маску для удаления всех "мелких" меток
    is_valid_basin = np.isin(labeled_basins, valid_labels)
    labeled_basins[~is_valid_basin] = 0 # Обнуляем метки, не прошедшие фильтр
    # --- КОНЕЦ ИСПРАВЛЕНИЯ ---

    # Исключаем озера, которые касаются края карты
    edge_labels = np.unique(np.concatenate((
        labeled_basins[0, :], labeled_basins[-1, :],
        labeled_basins[:, 0], labeled_basins[:, -1]
    )))

    lakes_created = 0
    # Итерируем только по ID оставшихся (крупных) озер
    for i in np.unique(labeled_basins):
        if i == 0 or i in edge_labels:
            continue

        basin_mask = (labeled_basins == i)
        # Находим точку "перелива" - самую низкую точку на границе впадины
        border_mask = binary_dilation(basin_mask) & ~basin_mask
        if not np.any(border_mask): continue

        pour_point_height = np.min(stitched_heights[border_mask])
        lake_mask = basin_mask & (stitched_heights < pour_point_height)
        if not np.any(lake_mask): continue

        # Вероятность появления озера зависит от влажности
        if stitched_humidity is not None:
            avg_humidity = float(np.mean(stitched_humidity[lake_mask]))
            base_chance = water_cfg.get("lake_chance_base", 0.1)
            multiplier = water_cfg.get("lake_chance_humidity_multiplier", 3.0)
            final_chance = base_chance + base_chance * avg_humidity * multiplier
            if rng.random() > final_chance:
                continue

        surface_set(stitched_surface, lake_mask, KIND_BASE_WATERBED)
        nav_set(stitched_nav, lake_mask, NAV_WATER)
        lakes_created += 1

    if lakes_created > 0:
        print(f"    -> Создано {lakes_created} высокогорных озер.")

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

    print("  -> [Hydrology] Генерация речной сети...")
    t0 = time.perf_counter()

    # Рассчитываем, куда потечет вода из каждой точки
    flow_dirs = build_d8_flow_directions(stitched_heights_ext)
    # Рассчитываем, сколько "единиц" воды протекает через каждую точку
    flow_map = flow_accumulation_from_dirs(stitched_heights_ext, flow_dirs)

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
        num_sources = 0 if not np.any(core_mask) else label_connected_components(core_mask)[1]
        if num_sources < target_sources:
            high_thr = mid_thr
        else:
            low_thr, best_mask = mid_thr, candidate_mask

    # Отфильтровываем слишком короткие ручейки
    labels, n = label_connected_components(best_mask)
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
    print(f"    -> Речная сеть создана за {(t1 - t0) * 1000:.1f} мс.")
    return best_mask