# Файл: game_engine/world/serialization.py
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Any, Tuple

from .road_types import ChunkRoadPlan


# --- Контракт 1: Метаданные для сервера ---
@dataclass
class RegionMetaContract:
    """
    Структура файла region_meta.json.
    Содержит всю информацию, нужную для генерации соседних регионов.
    """

    version: str = "1.0"
    scx: int = 0
    scz: int = 0
    world_seed: int = 0
    road_plan: Dict[Tuple[int, int], ChunkRoadPlan] = field(default_factory=dict)

    # --- НОВОЕ ПОЛЕ ---
    biome_probabilities: Dict[str, float] = field(default_factory=dict)

    edge_data: Dict[str, Any] = field(default_factory=dict)


# --- Контракт 2: Данные чанка для клиента ---
@dataclass
class ClientChunkContract:
    """
    Структура файла chunk.json (метаданные).
    Содержит только ту информацию, которая нужна клиенту для отрисовки и игры.
    """

    version: str = "chunk_v2_hex"
    cx: int = 0
    cz: int = 0
    grid: Dict[str, Any] = field(default_factory=dict)
    layer_files: Dict[str, str] = field(default_factory=dict)
    points_of_interest: List[Any] = field(default_factory=list)