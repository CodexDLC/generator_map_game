# game_engine/story_features/biome_rules.py
from __future__ import annotations
from typing import Any, Callable, Dict
import random
from ..core.constants import KIND_OBSTACLE, KIND_TREE, KIND_ROCK
from ..core.types import GenResult
from ..world_structure.regions import Region

# --- Тип для наших функций-генераторов биомов ---
BiomeRule = Callable[[GenResult, Any, Region], None]


def _apply_forest(result: GenResult, preset: Any, region: Region):
    """
    Создает лес из смеси деревьев и редких камней.
    """
    kind_grid = result.layers["kind"]
    scatter_mask = result.layers.get("scatter_mask", [])
    if not scatter_mask: return

    size = len(kind_grid)
    thinning_cfg = getattr(preset, "scatter", {}).get("thinning", {})
    if not thinning_cfg.get("enabled", False):
        _apply_swamp(result, preset, region)
        return

    min_dist = max(1, int(thinning_cfg.get("min_distance", 2)))
    possible_points = []
    for z in range(size):
        for x in range(size):
            if scatter_mask[z][x]:
                possible_points.append((x, z))

    rng = random.Random(result.stage_seeds.get("obstacles", 0))
    rng.shuffle(possible_points)

    placement_forbidden = [[False for _ in range(size)] for _ in range(size)]
    scatter_count = 0

    for x, z in possible_points:
        if placement_forbidden[z][x]:
            continue

        # --- НАЧАЛО ИЗМЕНЕНИЙ: Выбираем, что именно поставить ---
        # С вероятностью 95% это будет дерево, и с 5% - камень.
        if rng.random() < 0.95:
            kind_grid[z][x] = KIND_TREE
        else:
            kind_grid[z][x] = KIND_ROCK
        # --- КОНЕЦ ИЗМЕНЕНИЙ ---

        scatter_count += 1

        for dz in range(-min_dist, min_dist + 1):
            for dx in range(-min_dist, min_dist + 1):
                nx, nz = x + dx, z + dz
                if 0 <= nx < size and 0 <= nz < size:
                    placement_forbidden[nz][nx] = True

    if scatter_count > 0:
        print(f"--- SCATTER: Created {scatter_count} features for chunk ({result.cx}, {result.cz})")

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