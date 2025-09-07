# НОВЫЙ ФАЙЛ: game_engine/world_structure/context.py
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, Tuple, Any


@dataclass
class Region:
    """
    Чистая структура данных, описывающая регион.
    Не содержит логики, может безопасно импортироваться где угодно.
    """

    scx: int
    scz: int
    biome_type: str
    road_plan: Dict[Tuple[int, int], Any] = field(default_factory=dict)
