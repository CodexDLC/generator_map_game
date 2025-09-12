# game_engine_restructured/core/constants.py
from __future__ import annotations
from typing import Dict, Tuple

# =======================================================================
# СЛОЙ 1: ПОВЕРХНОСТИ (ЕДИНЫЙ СЕТ ДЛЯ TERRAIN3D)
# Все текстуры ландшафта, которые будут использоваться в одном сете.
# Сначала идут базовые слои, затем — слои для смешивания (детальные).
# =======================================================================

# --- Группа 1: Базовые поверхности ---
KIND_BASE_DIRT = "base_dirt"  # ID 0
KIND_BASE_GRASS = "base_grass"  # ID 1
KIND_BASE_SAND = "base_sand"  # ID 2
KIND_BASE_ROCK = "base_rock"  # ID 3
KIND_BASE_ROAD = "base_road"  # ID 4
KIND_BASE_CRACKED = "base_cracked"  # ID 5
KIND_BASE_WATERBED = "base_waterbed"  # ID 6

# --- Группа 2: Детальные (накладываемые) поверхности ---
KIND_OVERLAY_SNOW = "overlay_snow"  # ID 7
KIND_OVERLAY_LEAFS_GREEN = "overlay_leafs_green"  # ID 8
KIND_OVERLAY_LEAFS_AUTUMN = "overlay_leafs_autumn"  # ID 9
KIND_OVERLAY_FLOWERS = "overlay_flowers"  # ID 10
KIND_OVERLAY_DIRT_GRASS = "overlay_dirt_grass"  # ID 11
KIND_OVERLAY_DESERT_STONES = "overlay_desert_stones"  # ID 12


# --- Автоматическая генерация единого словаря ID ---
# Порядок здесь определяет финальные ID!
_SURFACE_KIND_NAMES: Tuple[str, ...] = (
    # Базовые
    KIND_BASE_DIRT,
    KIND_BASE_GRASS,
    KIND_BASE_SAND,
    KIND_BASE_ROCK,
    KIND_BASE_ROAD,
    KIND_BASE_CRACKED,
    KIND_BASE_WATERBED,
    # Детальные
    KIND_OVERLAY_SNOW,
    KIND_OVERLAY_LEAFS_GREEN,
    KIND_OVERLAY_LEAFS_AUTUMN,
    KIND_OVERLAY_FLOWERS,
    KIND_OVERLAY_DIRT_GRASS,
    KIND_OVERLAY_DESERT_STONES,
)

SURFACE_KIND_TO_ID: Dict[str, int] = {
    name: i for i, name in enumerate(_SURFACE_KIND_NAMES)
}
SURFACE_ID_TO_KIND: Dict[int, str] = {
    i: name for i, name in enumerate(_SURFACE_KIND_NAMES)
}
SURFACE_KINDS: Tuple[str, ...] = _SURFACE_KIND_NAMES

KIND_NAME_TO_ID = {v: k for k, v in SURFACE_ID_TO_KIND.items()}

# =======================================================================
# СЛОЙ НАВИГАЦИИ (остается без изменений)
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

# ===== NumPy dtypes для слоёв (если NumPy доступен) =====
try:
    import numpy as _np
except Exception:
    _np = None

SURFACE_DTYPE = _np.uint16 if _np else int
NAV_DTYPE     = _np.uint8  if _np else int

# ===== Обратные словари KIND -> ID (если не заданы где-то выше) =====
if "SURFACE_KIND_TO_ID" not in globals():
    SURFACE_KIND_TO_ID = {v: k for k, v in SURFACE_ID_TO_KIND.items()}
if "NAV_KIND_TO_ID" not in globals():
    NAV_KIND_TO_ID = {v: k for k, v in NAV_ID_TO_KIND.items()}

# ===== Универсальные преобразователи =====
def as_surface_id(kind_or_id):
    if isinstance(kind_or_id, int):
        return kind_or_id
    if _np and isinstance(kind_or_id, _np.integer):
        return int(kind_or_id)
    return SURFACE_KIND_TO_ID.get(kind_or_id, 0)

def as_nav_id(kind_or_id):
    if isinstance(kind_or_id, int):
        return kind_or_id
    if _np and isinstance(kind_or_id, _np.integer):
        return int(kind_or_id)
    return NAV_KIND_TO_ID.get(kind_or_id, 0)

# ===== Безопасная запись в массивы (принимают и строки, и ID) =====
def surface_fill(arr, kind_or_id):
    arr.fill(as_surface_id(kind_or_id))

def surface_set(arr, mask, kind_or_id):
    arr[mask] = as_surface_id(kind_or_id)

def nav_fill(arr, kind_or_id):
    arr.fill(as_nav_id(kind_or_id))

def nav_set(arr, mask, kind_or_id):
    arr[mask] = as_nav_id(kind_or_id)
