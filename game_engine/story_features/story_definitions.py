# game_engine/story_features/story_definitions.py
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, Tuple

@dataclass
class StructureExit:
    # Сторона выхода ('N', 'S', 'W', 'E')
    side: str
    # Позиция ворот в % от края (50 = центр)
    position_percent: int = 50

@dataclass
class StoryStructure:
    # Имя, например "Столица"
    name: str
    # Координаты чанка, где он находится
    cx: int
    cz: int
    # Словарь выходов
    exits: Dict[str, StructureExit] = field(default_factory=dict)

# --- НАШ РЕЕСТР ---
# Ключ - это кортеж (cx, cz) для быстрого поиска
STRUCTURE_REGISTRY: Dict[Tuple[int, int], StoryStructure] = {
    (0, 0): StoryStructure(
        name="Столица",
        cx=0,
        cz=0,
        exits={
            "N": StructureExit("N"),
            "S": StructureExit("S"),
            "W": StructureExit("W"),
            "E": StructureExit("E"),
        }
    ),
    (0, 3): StoryStructure(
        name="Портовый город",
        cx=0,
        cz=3,
        exits={
            # У порта есть только выходы на Запад и Восток
            "W": StructureExit("W"),
            "E": StructureExit("E"),
        }
    ),
}

def get_structure_at(cx: int, cz: int) -> StoryStructure | None:
    """Возвращает определение строения по координатам чанка, если оно там есть."""
    return STRUCTURE_REGISTRY.get((cx, cz))