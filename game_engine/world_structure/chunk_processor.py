# Файл: game_engine/world_structure/chunk_processor.py
from __future__ import annotations
import json
from pathlib import Path
from typing import Any, Dict

from ..core.types import GenResult
from ..core.preset import Preset
from .context import Region


def _load_raw_chunk_data(path: Path) -> Dict[str, Any]:
    """Вспомогательная функция для загрузки сырого чанка с диска."""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def process_chunk(
    preset: Preset, raw_chunk_path: Path, region_context: Region
) -> GenResult:
    """
    Главный конвейер детализации (ЭТАП 2).
    Временно отключены биомы и дороги для отладки базового ландшафта.
    """
    raw_data = _load_raw_chunk_data(raw_chunk_path)
    chunk = GenResult(**raw_data)

    # --- ВРЕМЕННО ОТКЛЮЧЕНО ДЛЯ ОТЛАДКИ ---
    # apply_biome_rules(chunk, preset, region_context)
    # build_local_roads(chunk, region_context, preset)
    # -------------------------------------

    # Просто выставляем флаги в False, т.к. этапы были пропущены
    chunk.capabilities["has_biomes"] = False
    chunk.capabilities["has_roads"] = False

    return chunk
