# Файл: .../steps/walkers/behaviors.py
from __future__ import annotations
import math
import random
from typing import List, Tuple, Dict
import numpy as np


def generate_perimeter_path(start_x: float, start_z: float, step_dist: float, bounds: Dict) -> List[
    Tuple[float, float]]:
    """Генерирует маршрут по периметру региона."""
    path = [(start_x, start_z)]
    current_x, current_z = start_x, start_z

    # Определяем 4 угла региона как путевые точки
    waypoints = [
        (bounds['min_x'], bounds['max_z']),  # NW
        (bounds['max_x'], bounds['max_z']),  # NE
        (bounds['max_x'], bounds['min_z']),  # SE
        (bounds['min_x'], bounds['min_z']),  # SW
        (bounds['min_x'], bounds['max_z'])  # Возвращаемся в начало для замыкания
    ]

    # Находим, с какого отрезка пути начать (ближайшего к start_x, start_z)
    # Это нужно, если стартовая точка не точно в углу. Для простоты пока опустим.

    for i in range(len(waypoints) - 1):
        target_x, target_z = waypoints[i + 1]

        # Движемся к цели, пока не достигнем ее
        while np.hypot(target_x - current_x, target_z - current_z) > step_dist:
            angle = math.atan2(target_z - current_z, target_x - current_x)
            current_x += math.cos(angle) * step_dist
            current_z += math.sin(angle) * step_dist
            path.append((current_x, current_z))

    return path


def generate_random_walk_path(start_x: float, start_z: float, step_dist: float, num_steps: int, bounds: Dict,
                              seed: int) -> List[Tuple[float, float]]:
    """Генерирует случайный, но детерминированный маршрут в пределах границ."""
    path = [(start_x, start_z)]
    current_x, current_z = start_x, start_z

    min_coord_x, max_coord_x = bounds['min_x'], bounds['max_x']
    min_coord_z, max_coord_z = bounds['min_z'], bounds['max_z']

    for step in range(num_steps - 1):  # -1, потому что первая точка уже есть
        # Простое случайное блуждание, но детерминированное
        next_dir_seed = seed + step * 251
        random.seed(next_dir_seed)
        move_angle_rad = random.uniform(0, 2 * math.pi)

        next_x = current_x + math.cos(move_angle_rad) * step_dist
        next_z = current_z + math.sin(move_angle_rad) * step_dist

        # Проверяем правило "не пересекай границу"
        if not (min_coord_x <= next_x <= max_coord_x and min_coord_z <= next_z <= max_coord_z):
            print("      -> Агент уперся в границу (во время планирования пути). Выбор другого направления.")
            # Пытаемся выбрать другое направление несколько раз
            for _ in range(5):
                random.seed(next_dir_seed + _ + 1)  # Меняем seed для новой попытки
                move_angle_rad = random.uniform(0, 2 * math.pi)
                next_x = current_x + math.cos(move_angle_rad) * step_dist
                next_z = current_z + math.sin(move_angle_rad) * step_dist
                if min_coord_x <= next_x <= max_coord_x and min_coord_z <= next_z <= max_coord_z:
                    break  # Нашли подходящее направление
            else:  # Если за 5 попыток не нашли, прерываем путь
                print("      -> Не удалось найти выход. Завершение.")
                break

        current_x, current_z = next_x, next_z
        path.append((current_x, current_z))

    return path