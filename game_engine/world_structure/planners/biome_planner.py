# game_engine/world_structure/planners/biome_planner.py
from __future__ import annotations
import random

# Импортируем утилиту для создания хэша, чтобы биомы были одинаковыми при одном и том же сиде
from ...core.utils.rng import hash64


def assign_biome_to_region(scx: int, scz: int, world_seed: int) -> str:
    """
    Определяет, какой биом будет присвоен целому региону.
    Логика основана на координатах региона и сиде мира, чтобы быть детерминированной.
    """

    # --- Особые правила для стартовой зоны ---
    if scx == 0 and scz == 0:
        # Стартовый регион всегда будет умеренным
        return "placeholder_biome"

    # --- Общие правила для остального мира ---

    # Создаем уникальный и постоянный "сид" для этого региона
    region_seed = hash64(world_seed, scx, scz)
    rng = random.Random(region_seed)

    # Примеры простой логики выбора. В будущем ее можно усложнить.
    choice = rng.random() # Случайное число от 0.0 до 1.0

    if choice < 0.4:
        # 40% шанс на густой лес
        return "dense_forest"
    elif choice < 0.8:
        # 40% шанс на скалистые равнины
        return "rocky_plains"
    else:
        # 20% шанс на умеренный биом по умолчанию
        return "placeholder_biome"