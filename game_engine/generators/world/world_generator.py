# ИСПРАВЛЕНО: game_engine/generators/world/world_generator.py
from __future__ import annotations
from typing import Any, Dict

from .._base.generator import BaseGenerator
from ...core.types import GenResult
from ...story_features import starting_zone_rules
from ...story_features.biome_rules import apply_biome_rules
from ...story_features.local_roads import build_local_roads

# --- ИЗМЕНЕНИЕ: Импортируем Region из нового чистого файла ---
from ...world_structure.context import Region


class WorldGenerator(BaseGenerator):
    # Конструктор остается, он наследует preset от BaseGenerator
    def generate(self, params: Dict[str, Any]) -> GenResult:
        raise NotImplementedError("This generator only details chunks via finalize_chunk.")

    def finalize_chunk(self, base_result: GenResult, region: Region) -> GenResult:
        """Принимает 'голый' чанк и 'одевает' его деталями."""
        apply_biome_rules(base_result, self.preset, region)
        build_local_roads(base_result, self.preset, region)

        if starting_zone_rules.get_structure_at(base_result.cx, base_result.cz):
            starting_zone_rules.apply_starting_zone_rules(base_result, self.preset)

        base_result.capabilities["has_biomes"] = True
        base_result.capabilities["has_roads"] = True
        return base_result