# Файл: game_engine/world/features/biome_rules.py
from __future__ import annotations
from typing import Any

# --- НАЧАЛО ИЗМЕНЕНИЙ ---

from ...core.types import GenResult
from ..context import Region
from .forests import ForestBrush
from .rocks import RockBrush

# --- КОНЕЦ ИЗМЕНЕНИЙ ---

# Реестр кисточек
BRUSH_REGISTRY = {
    "forests": ForestBrush,
    "rocks": RockBrush,
}

# Реестр биомов (наша "партитура")
BIOME_REGISTRY = {
    "placeholder_biome": [
        # В этом биоме терраформинга нет
        ("forests", {"min_distance": 2}),
        ("rocks", {"density": 0.05}),
    ],
    "canyon_lands": [
        # А в этом биоме мы сначала "вдавливаем" каньоны, а потом ставим камни
        (
            "terraform",
            {
                "rules": [
                    {
                        "enabled": True,
                        "type": "flatten",
                        "noise_from": 0.4,
                        "noise_to": 0.5,
                        "target_noise": 0.1,
                    }
                ]
            },
        ),
        ("rocks", {"density": 0.3}),
    ],
    "high_plateaus": [
        # А здесь - "выдавливаем" плато и сажаем редкий лес
        (
            "terraform",
            {
                "rules": [
                    {
                        "enabled": True,
                        "type": "remap",
                        "noise_from": 0.6,
                        "noise_to": 0.7,
                        "remap_to_from": 0.8,
                        "remap_to_to": 0.9,
                    }
                ]
            },
        ),
        ("forests", {"min_distance": 4}),
    ],
}


def apply_biome_rules(result: GenResult, preset: Any, region: Region):
    """
    Находит рецепт для биома и последовательно применяет все кисточки из него.
    """
    biome_recipe = BIOME_REGISTRY.get(
        region.biome_type, BIOME_REGISTRY["placeholder_biome"]
    )

    for brush_name, settings in biome_recipe:
        brush_class = BRUSH_REGISTRY.get(brush_name)
        if brush_class:
            brush_instance = brush_class(result, preset)
            brush_instance.apply(**settings)
