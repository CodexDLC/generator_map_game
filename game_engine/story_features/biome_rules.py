# ОБНОВИТЕ ФАЙЛ: game_engine/story_features/biome_rules.py
from __future__ import annotations
from typing import Any

from ..core.types import GenResult
# --- ИЗМЕНЕНИЕ: Импортируем Region из нового, чистого файла ---
from ..world_structure.context import Region
from .features.forests import ForestBrush
from .features.rocks import RockBrush


# Реестр кисточек
BRUSH_REGISTRY = {
    "forests": ForestBrush,
    "rocks": RockBrush,
}

# Реестр биомов (наша "партитура")
BIOME_REGISTRY = {
    "placeholder_biome": [
        ("forests", {"tree_rock_ratio": 0.95, "min_distance": 2}),
        ("rocks", {"density": 0.05, "near_slope_multiplier": 4.0}),
    ],
    "dense_forest": [
        ("forests", {"tree_rock_ratio": 0.98, "min_distance": 1}),
    ],
    "rocky_plains": [
        ("forests", {"tree_rock_ratio": 0.20, "min_distance": 4}),
        ("rocks", {"density": 0.3, "near_slope_multiplier": 2.0}),
    ],
}


def apply_biome_rules(result: GenResult, preset: Any, region: Region):
    """
    Находит рецепт для биома и последовательно применяет все кисточки из него.
    """
    biome_recipe = BIOME_REGISTRY.get(region.biome_type, BIOME_REGISTRY["placeholder_biome"])

    for brush_name, settings in biome_recipe:
        brush_class = BRUSH_REGISTRY.get(brush_name)
        if brush_class:
            brush_instance = brush_class(result, preset)
            brush_instance.apply(**settings)