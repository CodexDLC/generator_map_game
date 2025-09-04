# НОВЫЙ ФАЙЛ: game_engine/world_structure/chunk_processor.py
from __future__ import annotations
import json
from pathlib import Path
from typing import Any, Dict

from ..core.types import GenResult
from ..core.preset import Preset
from ..story_features.biome_rules import apply_biome_rules
from ..story_features.local_roads import build_local_roads
from ..story_features import starting_zone_rules
from .context import Region


def _load_raw_chunk_data(path: Path) -> Dict[str, Any]:
    """Вспомогательная функция для загрузки сырого чанка с диска."""
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def process_chunk(
    preset: Preset, # preset здесь остается, он нужен другим функциям
    raw_chunk_path: Path,
    region_context: Region
) -> GenResult:
    """
    Главный конвейер детализации (ЭТАП 2).
    Работает только с файлами. Не знает о RegionManager.
    """
    # 1. Загружаем сырые данные
    raw_data = _load_raw_chunk_data(raw_chunk_path)

    # 2. Восстанавливаем объект GenResult из сырых данных
    # (В будущем это можно будет сделать через более строгую сериализацию)
    chunk = GenResult(**raw_data)

    # 3. Последовательно применяем "инструменты-декораторы"
    apply_biome_rules(chunk, preset, region_context)
    build_local_roads(chunk, region_context)

    # Применяем правила для особых структур (городов)
    if starting_zone_rules.get_structure_at(chunk.cx, chunk.cz):
        starting_zone_rules.apply_starting_zone_rules(chunk, preset)

    # 4. Обновляем метаданные о том, что чанк прошел детализацию
    chunk.capabilities["has_biomes"] = True
    chunk.capabilities["has_roads"] = True

    # 5. Возвращаем финальный, "одетый" чанк
    return chunk