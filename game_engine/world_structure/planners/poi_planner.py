# game_engine/world_structure/planners/poi_planner.py
from __future__ import annotations
from typing import List, Tuple
import random

from ...core.constants import KIND_GROUND, KIND_SAND
from ..road_types import RoadWaypoint

POI_RECIPES = {
    "placeholder_biome": {
        "ruins_in_clearing": {
            "tile_types": [KIND_GROUND, KIND_SAND],
            "search_radius": 5,
            "min_density": 0.8,
            "poi_type": "ruin"
        }
    }
}


def _find_clearing(stitched_map: List[List[str]], recipe: dict, rng: random.Random) -> Tuple[int, int] | None:
    """Ищет подходящую поляну, используя детерминированный RNG."""
    height = len(stitched_map)
    width = len(stitched_map[0])
    radius = recipe["search_radius"]
    search_zone_margin = width // 4

    for _ in range(100):
        # --- ИЗМЕНЕНИЕ: Используем наш предсказуемый rng ---
        gx = rng.randint(search_zone_margin, width - search_zone_margin)
        gz = rng.randint(search_zone_margin, height - search_zone_margin)

        ground_tiles, total_tiles = 0, 0
        for z_offset in range(-radius, radius + 1):
            for x_offset in range(-radius, radius + 1):
                check_x, check_z = gx + x_offset, gz + z_offset
                if 0 <= check_x < width and 0 <= check_z < height:
                    if stitched_map[check_z][check_x] in recipe["tile_types"]:
                        ground_tiles += 1
                    total_tiles += 1

        if total_tiles > 0 and (ground_tiles / total_tiles) >= recipe["min_density"]:
            print(f"[POI_Planner] -> Found a suitable clearing at ({gx}, {gz})")
            return gx, gz
    return None


def plan_pois_for_region(stitched_map: List[List[str]], biome_type: str, seed: int) -> List[RoadWaypoint]:
    """
    Главная функция планировщика POI. Теперь использует seed.
    """
    pois = []
    recipe = POI_RECIPES.get(biome_type)
    if not recipe:
        return []

    print(f"[POI_Planner] -> Planning POIs for biome: {biome_type}")

    # --- ИЗМЕНЕНИЕ: Создаем детерминированный RNG ---
    rng_seed = seed ^ 0xCAFEF00D  # Смешиваем с константой для уникальности
    rng = random.Random(rng_seed)

    if "ruins_in_clearing" in recipe:
        clearing_pos = _find_clearing(stitched_map, recipe["ruins_in_clearing"], rng)
        if clearing_pos:
            pois.append(RoadWaypoint(pos=clearing_pos, is_structure=True))

    return pois