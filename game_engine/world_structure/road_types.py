from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Tuple

# Глобальные координаты тайла (не чанка)
GlobalCoord = Tuple[int, int]


@dataclass
class RoadWaypoint:
    """Опорная точка на глобальном маршруте дороги."""

    pos: GlobalCoord
    # Является ли точка "воротами" между чанками
    is_gate: bool = False
    # Является ли точка центром структуры (города)
    is_structure: bool = False


@dataclass
class ChunkRoadPlan:
    """Детализированный план дорог для одного чанка."""

    # Список опорных точек, которые нужно соединить внутри этого чанка
    waypoints: List[RoadWaypoint] = field(default_factory=list)
