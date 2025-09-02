# game_engine/core/constants.py
import math
from typing import Dict

# --- Базовые типы тайлов ---
KIND_GROUND = "ground"
KIND_OBSTACLE = "obstacle"
KIND_WATER = "water"
KIND_ROAD = "road"
KIND_VOID = "void"
KIND_SLOPE = "slope"
KIND_WALL = "wall"
KIND_BRIDGE = "bridge"
KIND_SAND = "sand"
KIND_TREE = "tree"
KIND_ROCK = "rock"

KIND_VALUES = (
    KIND_GROUND, KIND_OBSTACLE, KIND_WATER, KIND_ROAD, KIND_SLOPE,
    KIND_VOID, KIND_WALL, KIND_BRIDGE, KIND_SAND,
    KIND_TREE, KIND_ROCK # <-- Добавлено
)

# --- Маппинги для сериализации ---
KIND_TO_ID: Dict[str, int] = {
    KIND_GROUND: 0,
    KIND_OBSTACLE: 1,
    KIND_WATER: 2,
    KIND_ROAD: 3,
    KIND_VOID: 4,
    KIND_SLOPE: 5,
    KIND_WALL: 6,
    KIND_BRIDGE: 7,
    KIND_SAND: 8,
    KIND_TREE: 9,
    KIND_ROCK: 10,

}
ID_TO_KIND: Dict[int, str] = {v: k for k, v in KIND_TO_ID.items()}

# --- Палитра для рендера по умолчанию ---
DEFAULT_PALETTE: Dict[str, str] = {
    KIND_GROUND: "#7a9e7a",
    KIND_OBSTACLE: "#444444",
    KIND_WATER: "#3573b8",
    KIND_ROAD: "#d2b48c",
    KIND_SLOPE: "#9aa0a6",
    KIND_VOID: "#00000000",
    KIND_WALL: "#8B4513",
    KIND_BRIDGE: "#b8b8b8",
    KIND_SAND: "#e0cda8", #
    KIND_TREE: "#228B22",  #
    KIND_ROCK: "#808080",  #
}

# --- Базовая стоимость передвижения для поиска пути (A*) ---
DEFAULT_TERRAIN_FACTOR: Dict[str, float] = {
    KIND_GROUND: 1.0,
    KIND_ROAD: 0.6,
    KIND_BRIDGE: 0.6,
    KIND_SAND: 1.2,
    KIND_OBSTACLE: math.inf,
    KIND_WATER: math.inf,
    KIND_SLOPE: math.inf,
    KIND_VOID: math.inf,
    KIND_WALL: math.inf,
    KIND_TREE: math.inf,
    KIND_ROCK: math.inf,

}