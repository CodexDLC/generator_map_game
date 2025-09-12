from __future__ import annotations
from dataclasses import dataclass


@dataclass
class PlacedObject:
    """Структура для хранения информации о размещенном в мире объекте."""

    prefab_id: str
    center_q: int
    center_r: int
    rotation: float
    scale: float = 1.0
