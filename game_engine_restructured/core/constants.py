# game_engine_restructured/core/constants.py
from __future__ import annotations
from typing import Dict, Tuple

# =======================================================================
# СЛОЙ 1: ПОВЕРХНОСТИ (32 ID для control.r32)
# =======================================================================

# --- ID 0-3: ОБЩИЕ БАЗОВЫЕ ТИПЫ И ДОРОГИ ---
KIND_BASE_DIRT = "base_dirt"
KIND_BASE_ROCK = "base_rock"
KIND_BASE_SAND = "base_sand"
KIND_ROAD_PAVED = "road_paved"

# --- ID 4-7: БИОМ "УМЕРЕННЫЙ ЛЕС" (Temperate Forest) ---
KIND_FOREST_FLOOR = "forest_floor"
KIND_FOREST_GRASS = "forest_grass"
KIND_FOREST_FLOWERS = "forest_flowers"
KIND_FOREST_AUTUMN = "forest_autumn"

KIND_PLAINS_GRASS = "plains_grass"
KIND_PLAINS_FLOWERS = "plains_flowers"
KIND_PLAINS_DIRT = "plains_dirt"
KIND_PLAINS_STONES = "plains_stones"

KIND_SAVANNA_DRYGRASS = "savanna_drygrass"
KIND_SAVANNA_CRACKED = "savanna_cracked"
KIND_SAVANNA_ROCKY = "savanna_rocky"
KIND_SAVANNA_SAND = "savanna_sand"

KIND_DESERT_GROUND = "desert_ground"
KIND_DESERT_SAND = "desert_sand"
KIND_DESERT_STONES = "desert_stones"
KIND_DESERT_CRACKED = "desert_cracked_dark"

KIND_JUNGLE_DARKFLOOR = "jungle_darkfloor"
KIND_JUNGLE_LEAFS = "jungle_leafs"
KIND_JUNGLE_MUD = "jungle_mud"
KIND_JUNGLE_ROOTS = "jungle_roots"

KIND_TAIGA_MOSS = "taiga_moss"
KIND_TAIGA_NEEDLES = "taiga_needles"
KIND_TAIGA_SNOWDUST = "taiga_snowdust"
KIND_TAIGA_WETSTONE = "taiga_wetstone"

KIND_TUNDRA_SNOWGROUND = "tundra_snowground"
KIND_TUNDRA_ICEROCK = "tundra_icerock"
KIND_TUNDRA_FLOWERS = "tundra_flowers"
KIND_TUNDRA_FROZENDIRT = "tundra_frozendirt"

# --- Автоматическая генерация словарей ID ---
_SURFACE_KIND_NAMES: Tuple[str, ...] = (
    "base_dirt", "base_rock", "base_sand", "road_paved",
    "forest_floor", "forest_grass", "forest_flowers", "forest_autumn",
    "plains_grass", "plains_flowers", "plains_dirt", "plains_stones",
    "savanna_drygrass", "savanna_cracked", "savanna_rocky", "savanna_sand",
    "desert_ground", "desert_sand", "desert_stones", "desert_cracked_dark",
    "jungle_darkfloor", "jungle_leafs", "jungle_mud", "jungle_roots",
    "taiga_moss", "taiga_needles", "taiga_snowdust", "taiga_wetstone",
    "tundra_snowground", "tundra_icerock", "tundra_flowers", "tundra_frozendirt",
)
SURFACE_KIND_TO_ID: Dict[str, int] = {name: i for i, name in enumerate(_SURFACE_KIND_NAMES)}
SURFACE_ID_TO_KIND: Dict[int, str] = {i: name for i, name in enumerate(_SURFACE_KIND_NAMES)}
SURFACE_KINDS: Tuple[str, ...] = _SURFACE_KIND_NAMES

# =======================================================================
# СЛОЙ 2: НАВИГАЦИЯ (остается без изменений)
# =======================================================================
NAV_PASSABLE = "passable"
NAV_OBSTACLE = "obstacle_prop"
NAV_WATER = "water"
NAV_BRIDGE = "bridge"
NAV_KINDS = (NAV_PASSABLE, NAV_OBSTACLE, NAV_WATER, NAV_BRIDGE)
NAV_KIND_TO_ID: Dict[str, int] = {
    NAV_PASSABLE: 0,
    NAV_OBSTACLE: 1,
    NAV_WATER: 2,
    NAV_BRIDGE: 7,
}
NAV_ID_TO_KIND: Dict[int, str] = {v: k for k, v in NAV_KIND_TO_ID.items()}