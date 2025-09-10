# Файл: game_engine/world/chunk_processor.py
from __future__ import annotations
import json
from pathlib import Path
from typing import Any, Dict

# --- НАЧАЛО ИЗМЕНЕНИЙ ---

from ..core.types import GenResult
from ..core.preset import Preset
from .context import Region
from .features.biome_rules import apply_biome_rules
from .features.local_roads import build_local_roads
from .prefab_manager import PrefabManager
from .object_types import PlacedObject
from .grid_utils import generate_hex_map_from_pixels
from ..core.grid.hex import HexGridSpec

# --- КОНЕЦ ИЗМЕНЕНИЙ ---


def _load_raw_chunk_data(path: Path) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def process_chunk(
        preset: Preset, raw_chunk_path: Path, region_context: Region, prefab_manager: PrefabManager
) -> GenResult:
    raw_data = _load_raw_chunk_data(raw_chunk_path)

    # --- ВОЗВРАЩАЕМ ЛОГИКУ ВОССТАНОВЛЕНИЯ grid_spec ---
    grid_spec_data = raw_data.pop("grid_spec", None)
    chunk = GenResult(**raw_data)
    if grid_spec_data:
        chunk.grid_spec = HexGridSpec(**grid_spec_data)
    # ----------------------------------------------------

    chunk.placed_objects: list[PlacedObject] = []

    # Здесь в будущем будет обработка биомов и дорог
    # apply_biome_rules(...)
    # build_local_roads(...)

    # --- ВОЗВРАЩАЕМ ГЕНЕРАЦИЮ ДАННЫХ ДЛЯ КАРТЫ ГЕКСОВ ---
    if chunk.grid_spec:
        # Вот эта строка выведет лог, который вы ищете
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