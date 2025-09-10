# pygame_tester/palette.py
from typing import Dict

# Палитра для pygame_tester.
# Определяет по одному основному цвету для каждого биома для визуальной отладки.
PYGAME_PALETTE: Dict[str, str] = {
    # --- Общие типы ---
    "base_dirt": "#8B4513",        # Коричневый (грязь)
    "base_rock": "#9aa0a6",        # Серый (скалы)
    "base_sand": "#e0cda8",        # Песочный
    "road": "#d2b48c",             # Дорога

    # --- Основные цвета биомов ---
    "forest_floor": "#6A7B44",     # Умеренный лес (зеленый)
    "plains_grass": "#90A959",     # Равнины (светло-зеленый)
    "savanna_drygrass": "#B7A649", # Саванна (желтоватый)
    "desert_ground": "#D8B578",    # Пустыня (песочно-оранжевый)
    "jungle_darkfloor": "#4E5731", # Джунгли (темно-зеленый)
    "taiga_moss": "#5F6F4F",       # Тайга (серо-зеленый)
    "tundra_snowground": "#E1E1E1",# Тундра (светло-серый, почти белый)

    # --- Навигация ---
    "water": "#3573b8",
    "bridge": "#b8b8b8",
    "obstacle_prop": "#444444",
    "void": "#0F0F19",             # Цвет фона
}