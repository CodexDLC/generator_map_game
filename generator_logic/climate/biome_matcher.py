# generator_logic/climate/biome_matcher.py
from __future__ import annotations
from typing import Dict

def calculate_biome_probabilities(
    avg_temp_c: float,
    avg_humidity: float,
    biomes_definition: Dict
) -> Dict[str, float]:
    """
    Рассчитывает вероятность каждого биома на основе климатических показателей.

    Args:
        avg_temp_c: Средняя температура в регионе.
        avg_humidity: Средняя влажность в регионе (0..1).
        biomes_definition: Словарь с описанием идеальных условий для каждого биома.

    Returns:
        Словарь с вероятностями: {'biome_name': 0.75, ...}
    """
    probabilities: Dict[str, float] = {}
    total_score = 0.0

    for biome_id, biome_data in biomes_definition.items():
        # Простое евклидово расстояние в пространстве "температура-влажность"
        # Для влажности умножаем на 100, чтобы сделать оси сопоставимыми
        temp_diff = (avg_temp_c - biome_data.get("ideal_temp_c", 15.0))
        humidity_diff = (avg_humidity * 100 - biome_data.get("ideal_humidity", 0.5) * 100)

        # Чем меньше расстояние, тем выше "счет" (score)
        distance_sq = temp_diff**2 + humidity_diff**2
        score = 1.0 / (1.0 + distance_sq * 0.01) # Множитель 0.01 для масштабирования

        probabilities[biome_id] = score
        total_score += score

    # Нормализуем, чтобы сумма вероятностей была равна 1.0
    if total_score > 0:
        for biome_id in probabilities:
            probabilities[biome_id] /= total_score

    return probabilities