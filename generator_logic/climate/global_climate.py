# ЗАМЕНА ВСЕГО ФАЙЛА: generator_logic/climate/global_climate.py
from __future__ import annotations
from typing import Dict, Tuple
import numpy as np
import math
from . import global_models

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
    latitude_factor = np.abs(xyz_coords[:, 2])
    base_temp = params.get("avg_temp_c", 15.0)
    equator_pole_diff = params.get("axis_tilt_deg", 23.5) * 1.5
    latitudinal_temp = (base_temp + equator_pole_diff / 3.0) - latitude_factor * equator_pole_diff

    # 2. Коррекция на высоту (чем выше, тем холоднее)
    # --- ИСПРАВЛЕНИЕ ЗДЕСЬ ---
    # Убеждаемся, что heights_m - это 1D массив, и выполняем операцию.
    # Ошибка возникала, если сюда случайно передавался 2D/3D массив.
    altitude_corrected_temp = latitudinal_temp + heights_m.flatten() * -0.0065

    # 3. Коррекция на сушу/океан
    land_ocean_correction = np.zeros_like(altitude_corrected_temp)
    land_warming = params.get("land_warming_effect_c", 2.5)
    land_ocean_correction[is_land_mask] = land_warming
    land_ocean_correction[~is_land_mask] = -land_warming / 2.0

    final_temp = altitude_corrected_temp + land_ocean_correction
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
    latitude_rad = np.arcsin(np.clip(xyz_coords[:, 2], -1.0, 1.0))
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
    return wind_vectors


def transport_humidity(
        xyz_coords: np.ndarray, # <--- ИСПРАВЛЕНИЕ: Явная передача координат
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
    for _ in range(iterations):
        next_humidity = humidity.copy()
        for i in range(len(humidity)):
            total_influx = 0.0
            count = 0
            for neighbor_idx in neighbors[i]:
                direction_vec = xyz_coords[i] - xyz_coords[neighbor_idx]
                wind_alignment = np.dot(wind_vectors[i], direction_vec)
                if wind_alignment > 0:
                    total_influx += humidity[neighbor_idx] * wind_alignment
                    count += 1
            if count > 0:
                avg_influx = total_influx / count
                next_humidity[i] = (humidity[i] + avg_influx) / 2.0
        humidity = next_humidity * damping
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
    temperature_map = calculate_global_temperature(xyz_coords, heights_m, is_land_mask, params)

    initial_humidity = np.zeros(xyz_coords.shape[0], dtype=np.float32)
    initial_humidity[~is_land_mask] = 1.0

    wind_vectors = get_global_wind_vectors(xyz_coords)

    # ИСПРАВЛЕНИЕ: Передаем xyz_coords в transport_humidity
    humidity_transported = transport_humidity(xyz_coords, initial_humidity, wind_vectors, neighbors)

    max_h = np.max(heights_m)
    if max_h > 1.0:
        height_factor = np.clip(1.0 - (heights_m / max_h), 0.5, 1.0)
        humidity_final = humidity_transported * height_factor
    else:
        humidity_final = humidity_transported

    return {
        "temperature": temperature_map,
        "humidity": np.clip(humidity_final, 0.0, 1.0),
    }