# НОВЫЙ ФАЙЛ: game_engine/world_structure/chunk_processor.py
from __future__ import annotations
import json
from pathlib import Path
from typing import Any, Dict

from ..core.types import GenResult
from ..core.preset import Preset
from ..story_features.biome_rules import apply_biome_rules
from ..story_features.local_roads import build_local_roads
from .context import Region


def _load_raw_chunk_data(path: Path) -> Dict[str, Any]:
    """Вспомогательная функция для загрузки сырого чанка с диска."""
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def process_chunk(
        preset: Preset,
        raw_chunk_path: Path,
        region_context: Region
) -> GenResult:
    """
    Главный конвейер детализации (ЭТАП 2).
    """
    raw_data = _load_raw_chunk_data(raw_chunk_path)
    chunk = GenResult(**raw_data)

    apply_biome_rules(chunk, preset, region_context)

    # --- ИЗМЕНЕНИЕ: Передаем 'preset' в build_local_roads ---
    build_local_roads(chunk, region_context, preset)

    chunk.capabilities["has_biomes"] = True
    chunk.capabilities["has_roads"] = True

    return chunk