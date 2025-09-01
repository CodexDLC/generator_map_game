# В файле engine/worldgen_core/base/constants.py
from typing import Dict

KIND_GROUND = "ground"
KIND_OBSTACLE = "obstacle"
KIND_WATER = "water"
KIND_ROAD = "road"
KIND_VOID = "void"
KIND_SLOPE = "slope"
KIND_WALL = "wall" # <<< ДОБАВИТЬ ЭТУ СТРОКУ

KIND_VALUES = (KIND_GROUND, KIND_OBSTACLE, KIND_WATER, KIND_ROAD, KIND_SLOPE, KIND_VOID, KIND_WALL) # <<< ДОБАВИТЬ СЮДА KIND_WALL

KIND_TO_ID: Dict[str, int] = {
    KIND_GROUND: 0,
    KIND_OBSTACLE: 1,
    KIND_WATER: 2,
    KIND_ROAD: 3,
    KIND_VOID: 4,
    KIND_SLOPE: 5,
    KIND_WALL: 6, # <<< ДОБАВИТЬ ЭТУ СТРОКУ
}

ID_TO_KIND: Dict[int, str] = {v: k for k, v in KIND_TO_ID.items()}

DEFAULT_PALETTE: Dict[str, str] = {
    KIND_GROUND:  "#7a9e7a",
    KIND_OBSTACLE:"#444444",
    KIND_WATER:   "#3573b8",
    KIND_ROAD:    "#d2b48c",
    KIND_SLOPE:   "#9aa0a6",
    KIND_VOID:    "#00000000",
    KIND_WALL:    "#808080", # <<< ДОБАВИТЬ ЭТУ СТРОКУ (серый цвет для стены)
}