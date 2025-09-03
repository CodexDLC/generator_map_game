# game_engine/story_features/biome_rules.py
from __future__ import annotations
from typing import Any, Callable, Dict

from ..core.constants import KIND_OBSTACLE
from ..core.types import GenResult
from ..world_structure.regions import Region

BiomeRule = Callable[[GenResult, Any, Region], None]

def _apply_forest(result: GenResult, preset: Any, region: Region):
    """
    Определяет, что это лесной биом, но не размещает объекты.
    """
    # Этот код теперь просто служит заглушкой,
    # так как генерация леса будет происходить в другом файле
    pass


def _apply_swamp(result: GenResult, preset: Any, region: Region):
    """
    Применяет сырую маску 'пятен' как есть, создавая сплошные непроходимые болота.
    """
    kind_grid = result.layers["kind"]
    scatter_mask = result.layers.get("scatter_mask", [])
    if not scatter_mask: return

    size = len(kind_grid)
    for z in range(size):
        for x in range(size):
            if scatter_mask[z][x]:
                # В оригинальном коде, болота были KIND_OBSTACLE
                kind_grid[z][x] = KIND_OBSTACLE


# --- НАШ РЕЕСТР БИОМОВ ---
BIOME_REGISTRY: Dict[str, BiomeRule] = {
    "placeholder_biome": _apply_forest,  # <-- По умолчанию используем лес
    "forest": _apply_forest,
    "swamp": _apply_swamp,
}


# --- Главная функция-фабрика ---
def apply_biome_rules(result: GenResult, preset: Any, region: Region):
    """
    Находит в реестре нужную функцию по имени биома и вызывает ее.
    """
    # Находим нужную функцию в реестре. Если не нашли, используем правило по умолчанию.
    rule_function = BIOME_REGISTRY.get(region.biome_type, BIOME_REGISTRY["placeholder_biome"])

    # Вызываем найденную функцию
    rule_function(result, preset, region)