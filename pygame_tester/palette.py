# pygame_tester/palette.py
from typing import Dict

# Палитра для pygame_tester.
PYGAME_PALETTE: Dict[str, str] = {
    # --- Базовые слои ---
    "base_dirt": "#8B4513",
    "base_grass": "#90A959",
    "base_sand": "#e0cda8",
    "base_rock": "#9aa0a6",
    "base_road": "#6E6E6E", # Брусчатка
    "base_cracked": "#B7A649",
    "base_waterbed": "#A2A2A2",

    # --- Детальные слои (могут понадобиться для отладки) ---
    "overlay_snow": "#E1E1E1",
    "overlay_leafs_green": "#6A7B44",
    "overlay_leafs_autumn": "#C06B3E",
    "overlay_flowers": "#D2A1D2",
    "overlay_dirt_grass": "#7C9A54",
    "overlay_desert_stones": "#C8B578",

    # --- Навигация ---
    "water": "#3573b8",
    "bridge": "#b8b8b8",
    "obstacle_prop": "#444444",
    "void": "#0F0F19",
}