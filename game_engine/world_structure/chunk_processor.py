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
from .object_types import PlacedObject
# --- НОВЫЙ ИМПОРТ ---
from .grid_utils import generate_hex_map_from_pixels


def _load_raw_chunk_data(path: Path) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def process_chunk(
        preset: Preset, raw_chunk_path: Path, region_context: Region, prefab_manager: PrefabManager
) -> GenResult:
    raw_data = _load_raw_chunk_data(raw_chunk_path)
    chunk = GenResult(**raw_data)

    chunk.placed_objects: list[PlacedObject] = []

    # ... (вызовы apply_biome_rules и build_local_roads) ...

    # --- ГЕНЕРАЦИЯ ДАННЫХ ДЛЯ КАРТЫ ГЕКСОВ ---
    if chunk.grid_spec:
        print(f"  -> Generating server hex map for chunk ({chunk.cx},{chunk.cz})...")
        chunk.hex_map_data = generate_hex_map_from_pixels(
            chunk.grid_spec,
            chunk.layers["surface"],
            chunk.layers["navigation"],
            chunk.layers["height_q"]["grid"]
        )
    # ------------------------------------------

    chunk.capabilities["has_biomes"] = False
    chunk.capabilities["has_roads"] = False

    return chunk