# game_engine/core/constants.py
from __future__ import annotations
from typing import Dict

# =======================================================================
# СЛОЙ 1: ПОВЕРХНОСТИ (ДЛЯ TERRAIN3D И ВИЗУАЛИЗАЦИИ)
# =======================================================================

KIND_GROUND = "ground"
KIND_SAND = "sand"
KIND_ROAD = "road"
KIND_SLOPE = "slope"
KIND_FOREST_GROUND = "forest_ground"
# --- УДАЛЕНО: KIND_VOID ---
KIND_DEBUG_A = "debug_a"
KIND_DEBUG_B = "debug_b"

# Список всех возможных ПОВЕРХНОСТЕЙ
SURFACE_KINDS = (KIND_GROUND, KIND_SAND, KIND_ROAD, KIND_SLOPE, KIND_FOREST_GROUND, KIND_DEBUG_A, KIND_DEBUG_B)

# ID для записи в control.r32. Идут строго по порядку от 0.
SURFACE_KIND_TO_ID: Dict[str, int] = {
    KIND_GROUND: 0,
    KIND_SAND: 1,
    KIND_ROAD: 2,
    KIND_SLOPE: 3,
    KIND_FOREST_GROUND: 4,
    # Следующий ID будет 5
    KIND_DEBUG_A: 5,
    KIND_DEBUG_B: 6,
}
SURFACE_ID_TO_KIND: Dict[int, str] = {v: k for k, v in SURFACE_KIND_TO_ID.items()}


# =======================================================================
# СЛОЙ 2: НАВИГАЦИЯ (ДЛЯ PATHFINDER И СЕРВЕРА)
# =======================================================================

NAV_PASSABLE = "passable"
NAV_OBSTACLE = "obstacle_prop"
NAV_WATER = "water"
NAV_BRIDGE = "bridge"

# Список всех возможных НАВИГАЦИОННЫХ маркеров
NAV_KINDS = (NAV_PASSABLE, NAV_OBSTACLE, NAV_WATER, NAV_BRIDGE)

# ID для записи в nav_grid в chunk.rle.json.
NAV_KIND_TO_ID: Dict[str, int] = {
    NAV_PASSABLE: 0,
    NAV_OBSTACLE: 1,
    NAV_WATER: 2,
    NAV_BRIDGE: 7,
}
NAV_ID_TO_KIND: Dict[int, str] = {v: k for k, v in NAV_KIND_TO_ID.items()}


# =======================================================================
# ОБЩИЕ КОНСТАНТЫ (ПАЛИТРА, СТОИМОСТЬ ПУТИ)
# =======================================================================

# Палитра для pygame_tester.
DEFAULT_PALETTE: Dict[str, str] = {
    # Поверхности
    KIND_GROUND: "#7a9e7a",
    KIND_ROAD: "#d2b48c",
    KIND_SLOPE: "#9aa0a6",
    KIND_SAND: "#e0cda8",
    KIND_FOREST_GROUND: "#556B2F",
    # Навигационные маркеры (для отладки)
    NAV_WATER: "#3573b8",
    NAV_BRIDGE: "#b8b8b8",
    NAV_OBSTACLE: "#444444",
}

# Стоимость передвижения. Зависит от ТИПА ПОВЕРХНОСТИ.
DEFAULT_TERRAIN_FACTOR: Dict[str, float] = {
    KIND_GROUND: 1.0,
    KIND_FOREST_GROUND: 1.1,
    KIND_ROAD: 0.6,
    KIND_SAND: 1.2,
    KIND_SLOPE: 5.0,
}
