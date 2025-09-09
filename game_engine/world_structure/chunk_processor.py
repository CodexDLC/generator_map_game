# Файл: game_engine/world_structure/chunk_processor.py
from __future__ import annotations
import json
from pathlib import Path
from typing import Any, Dict

from ..core.types import GenResult
from ..core.preset import Preset
from .context import Region
from ..story_features.biome_rules import apply_biome_rules
from ..story_features.local_roads import build_local_roads
from .prefab_manager import PrefabManager
from .object_types import PlacedObject  # <-- Импортируем наш новый тип


def _load_raw_chunk_data(path: Path) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def process_chunk(
        preset: Preset, raw_chunk_path: Path, region_context: Region, prefab_manager: PrefabManager
) -> GenResult:
    raw_data = _load_raw_chunk_data(raw_chunk_path)
    chunk = GenResult(**raw_data)

    # --- ДОБАВЛЕНО: Подготавливаем список для объектов ---
    chunk.placed_objects: list[PlacedObject] = []

    # --- ВРЕМЕННО ОТКЛЮЧЕНО, ПОКА МЫ НЕ ПЕРЕДЕЛАЕМ КИСТИ ---
    # print("!!! WARNING: Biome and road brushes are temporarily disabled for refactoring.")
    # apply_biome_rules(chunk, preset, region_context, prefab_manager)
    # build_local_roads(chunk, region_context, preset)
    # --------------------------------------------------------

    chunk.capabilities["has_biomes"] = False
    chunk.capabilities["has_roads"] = False

    return chunk