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
    # Сюда мы будем добавлять планы биомов, рек и т.д.
    road_plan: Dict[Tuple[int, int], ChunkRoadPlan] = field(default_factory=dict)
    # Можно добавить информацию о "швах" на границах для биомов
    edge_data: Dict[str, Any] = field(default_factory=dict)


# --- Контракт 2: Данные чанка для клиента ---
@dataclass
class ClientChunkContract:
    """
    Структура файла chunk_X_Y.json.
    Содержит только ту информацию, которая нужна клиенту для отрисовки и игры.
    """

    version: str = "1.0"
    cx: int = 0
    cz: int = 0
    # Данные о тайлах. В будущем тайл станет словарем.
    layers: Dict[str, Any] = field(default_factory=dict)
    # Другие данные для клиента (точки интереса, квесты и т.д.)
    points_of_interest: List[Any] = field(default_factory=list)
