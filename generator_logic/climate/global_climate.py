# ЗАМЕНА ВСЕГО ФАЙЛА: generator_logic/climate/global_climate.py
from __future__ import annotations
from typing import Dict, Tuple
import numpy as np
import math
import logging
from . import global_models
from editor.utils.diag import diag_array

# Получаем логгер для этого модуля
logger = logging.getLogger(__name__)


# ==============================================================================
# --- ШАГ 1: УЛУЧШЕННАЯ МОДЕЛЬ ТЕМПЕРАТУРЫ ---
# ==============================================================================

def calculate_global_temperature(
        xyz_coords: np.ndarray,
        heights_m: np.ndarray,
        is_land_mask: np.ndarray,
        params: dict
) -> np.ndarray:
    """
    Рассчитывает глобальную карту температур, учитывая широту, высоту и влияние суши/океана.
    """
    # 1. Базовая температура от широты
    latitude_factor = np.abs(xyz_coords[:, 1])
    base_temp = params.get("avg_temp_c", 15.0)
    equator_pole_diff = params.get("axis_tilt_deg", 23.5) * 1.5
    latitudinal_temp = (base_temp + equator_pole_diff / 3.0) - latitude_factor * equator_pole_diff

    # 2. Коррекция на высоту (чем выше, тем холоднее)
    heights_m_scalar = heights_m
    if heights_m.ndim > 1:
        heights_m_scalar = heights_m.flatten()

    # Убедимся, что размеры совпадают после всех преобразований
    if latitudinal_temp.shape != heights_m_scalar.shape:
        # Если размеры не совпадают, это критическая ошибка, которую нужно исправить в источнике данных.
        # В качестве временного решения можно попытаться обрезать больший массив, но это скроет проблему.
        logger.error(
            f"Критическая ошибка размерности: Температура {latitudinal_temp.shape} != Высота {heights_m_scalar.shape}")
        # Возвращаем базовую температуру, чтобы избежать падения
        return latitudinal_temp.astype(np.float32)

    altitude_corrected_temp = latitudinal_temp + heights_m_scalar * -0.0065

    # 3. Коррекция на сушу/океан
    land_ocean_correction = np.zeros_like(altitude_corrected_temp)
    land_warming = params.get("land_warming_effect_c", 2.5)

    # --- ИСПРАВЛЕНИЕ ЗДЕСЬ ---
    # Приводим маску к одномерному виду, чтобы она соответствовала массиву температур
    is_land_mask_flat = is_land_mask.flatten()

    # Убедимся, что размер маски соответствует
    if land_ocean_correction.shape == is_land_mask_flat.shape:
        land_ocean_correction[is_land_mask_flat] = land_warming
        land_ocean_correction[~is_land_mask_flat] = -land_warming / 2.0
    else:
        logger.error(
            f"Ошибка размерности маски: Массив {land_ocean_correction.shape} != Маска {is_land_mask_flat.shape}")

    final_temp = altitude_corrected_temp + land_ocean_correction

    # --- ЛОГИРОВАНИЕ ---
    diag_array(final_temp, name="final_temperature")

    return final_temp.astype(np.float32)


# ==============================================================================
# --- ШАГ 2: МОДЕЛЬ ГЛОБАЛЬНЫХ ВЕТРОВ И ВЛАЖНОСТИ ---
# ==============================================================================

def get_global_wind_vectors(xyz_coords: np.ndarray) -> np.ndarray:
    """
    Возвращает вектор ветра (в 3D) для каждой точки на сфере,
    симулируя три ячейки циркуляции.
    """
    n_points = xyz_coords.shape[0]
    wind_vectors = np.zeros((n_points, 3), dtype=np.float32)
    latitude_rad = np.arcsin(np.clip(xyz_coords[:, 1], -1.0, 1.0))
    hadley_cell_limit = math.radians(30)
    ferrel_cell_limit = math.radians(60)

    mask_hadley = np.abs(latitude_rad) < hadley_cell_limit
    wind_vectors[mask_hadley, 0] = -1.0

    mask_ferrel = (np.abs(latitude_rad) >= hadley_cell_limit) & (np.abs(latitude_rad) < ferrel_cell_limit)
    wind_vectors[mask_ferrel, 0] = 1.0

    mask_polar = np.abs(latitude_rad) >= ferrel_cell_limit
    wind_vectors[mask_polar, 0] = -1.0

    wind_vectors[mask_hadley, 2] = -np.sign(latitude_rad[mask_hadley]) * 0.5
    wind_vectors[mask_ferrel, 2] = np.sign(latitude_rad[mask_ferrel]) * 0.5

    norms = np.linalg.norm(wind_vectors, axis=1, keepdims=True)
    non_zero = norms.flatten() > 1e-6
    wind_vectors[non_zero] /= norms[non_zero]

    # --- ЛОГИРОВАНИЕ ---
    diag_array(wind_vectors, name="global_wind_vectors")

    return wind_vectors


def transport_humidity(
        xyz_coords: np.ndarray,
        initial_humidity: np.ndarray,
        wind_vectors: np.ndarray,
        neighbors: list[list[int]],
        iterations: int = 5,
        damping: float = 0.98
) -> np.ndarray:
    """
    Симулирует перенос влаги по ветру с помощью простого итеративного метода.
    """
    humidity = initial_humidity.copy()
    for i in range(iterations):
        next_humidity = humidity.copy()
        for j in range(len(humidity)):
            # Пропускаем океаны, они всегда источник максимальной влажности
            if initial_humidity[j] >= 1.0:
                continue

            total_influx = 0.0
            count = 0
            for neighbor_idx in neighbors[j]:
                # Вектор от соседа к текущей точке
                direction_vec = xyz_coords[j] - xyz_coords[neighbor_idx]
                # Проекция ветра на направление к нам
                wind_alignment = np.dot(wind_vectors[j], direction_vec)

                # Если ветер дует ОТ соседа К нам, учитываем его влажность
                if wind_alignment > 0:
                    total_influx += humidity[neighbor_idx] * wind_alignment
                    count += 1

            if count > 0:
                avg_influx = total_influx / count
                # --- ИЗМЕНЕНИЕ ЛОГИКИ ---
                # Даем больше веса приходящей влаге, чтобы она быстрее распространялась
                next_humidity[j] = humidity[j] * 0.6 + avg_influx * 0.4

        humidity = np.clip(next_humidity * damping, 0.0, 1.0)  # Применяем затухание и ограничитель

        if (i + 1) % 2 == 0:
            logger.debug(
                f"Humidity transport, iteration {i + 1}/{iterations}: min={np.min(humidity):.3f}, max={np.max(humidity):.3f}")

    diag_array(humidity, name="transported_humidity")
    return humidity


# ==============================================================================
# --- ШАГ 3: ГЛАВНАЯ ФУНКЦИЯ-ОРКЕСТРАТОР ---
# ==============================================================================

def orchestrate_global_climate_simulation(
        xyz_coords: np.ndarray,
        heights_m: np.ndarray,
        is_land_mask: np.ndarray,
        neighbors: list[list[int]],
        params: dict
) -> Dict[str, np.ndarray]:
    """
    Выполняет полную симуляцию глобального климата.
    """
    logger.debug("--- Starting Global Climate Simulation ---")
    temperature_map = calculate_global_temperature(xyz_coords, heights_m, is_land_mask, params)

    initial_humidity = np.zeros(xyz_coords.shape[0], dtype=np.float32)
    # --- ИСПРАВЛЕНИЕ: также приводим маску к 1D ---
    initial_humidity[~is_land_mask.flatten()] = 1.0
    diag_array(initial_humidity, name="initial_humidity")

    wind_vectors = get_global_wind_vectors(xyz_coords)

    humidity_transported = transport_humidity(xyz_coords, initial_humidity, wind_vectors, neighbors)

    heights_m_scalar = heights_m
    if heights_m.ndim > 1:
        heights_m_scalar = heights_m.flatten()

    max_h = np.max(heights_m_scalar)
    if max_h > 1.0:
        height_factor = np.clip(1.0 - (heights_m_scalar / max_h), 0.5, 1.0)
        humidity_final = humidity_transported * height_factor
    else:
        humidity_final = humidity_transported

    logger.debug("--- Global Climate Simulation Finished ---")
    diag_array(humidity_final, name="final_humidity")

    return {
        "temperature": temperature_map,
        "humidity": np.clip(humidity_final, 0.0, 1.0),
    }