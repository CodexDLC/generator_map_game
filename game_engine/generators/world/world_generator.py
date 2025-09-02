# game_engine/generators/world/world_generator.py
from __future__ import annotations
from typing import Any, Dict

from .._base.generator import BaseGenerator
from ...core.types import GenResult
from ...story_features import starting_zone_rules
from ...story_features.biome_rules import apply_biome_rules  # <<< Изменили импорт
from ...world_structure.regions import RegionManager  # <<< Добавили импорт


class WorldGenerator(BaseGenerator):
    # --- НАЧАЛО ИЗМЕНЕНИЙ ---
    def __init__(self, preset: Any, region_manager: RegionManager):
        super().__init__(preset)
        self.region_manager = region_manager

    # --- КОНЕЦ ИЗМЕНЕНИЙ ---

    def generate(self, params: Dict[str, Any]) -> GenResult:
        result = super().generate(params)

        cx = params.get("cx", 0)
        cz = params.get("cz", 0)

        # --- НАЧАЛО ИЗМЕНЕНИЙ: Получаем данные о биоме из RegionManager ---
        region = self.region_manager.get_region_data(
            *self.region_manager.get_region_coords_from_chunk_coords(cx, cz)
        )

        # Вызываем главную функцию, которая сама разберется, какое правило применить
        apply_biome_rules(result, self.preset, region)
        # --- КОНЕЦ ИЗМЕНЕНИЙ ---

        is_starting_zone = (
                params.get("world_id") == "world_location" and
                -1 <= cx <= 1 and
                -1 <= cz <= 1
        )

        if is_starting_zone:
            starting_zone_rules.apply_starting_zone_rules(result, self.preset)

        return result