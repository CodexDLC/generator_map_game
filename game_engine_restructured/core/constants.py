# ==============================================================================
# Файл: game_engine_restructured/core/constants.py
# Назначение: Глобальные константы проекта (ID текстур, типы навигации).
# ВЕРСИЯ 2.0: С жестко заданными ID для интеграции с движком.
# ==============================================================================
from __future__ import annotations
from typing import Dict, Tuple

import numpy as np

# =======================================================================
# СЛОЙ 1: ПОВЕРХНОСТИ (SURFACES)
# =======================================================================

# --- Шаг 1: Определяем строковые константы для удобства в коде Python ---
# (Эти строки - просто для читаемости, реальные ID задаются ниже)
KIND_BASE_DIRT = "base_dirt"
KIND_BASE_GRASS = "base_grass"
KIND_BASE_SAND = "base_sand"
KIND_BASE_ROCK = "base_rock"
KIND_BASE_ROAD = "base_road"
KIND_BASE_CRACKED = "base_cracked"
KIND_BASE_WATERBED = "base_waterbed"
KIND_OVERLAY_SNOW = "overlay_snow"
KIND_OVERLAY_LEAFS_GREEN = "overlay_leafs_green"
KIND_OVERLAY_LEAFS_AUTUMN = "overlay_leafs_autumn"
KIND_OVERLAY_FLOWERS = "overlay_flowers"
KIND_OVERLAY_DIRT_GRASS = "overlay_dirt_grass"
KIND_OVERLAY_DESERT_STONES = "overlay_desert_stones"

# --- Шаг 2: Создаем ЕДИНЫЙ СЛОВАРЬ ID. Это "центр правды". ---
# Ты можешь менять эти цифры, чтобы они соответствовали настройкам в Godot.
# Главное, чтобы они были в диапазоне от 0 до 31.
SURFACE_KIND_TO_ID: Dict[str, int] = {
    # --- Базовые слои ---
    KIND_BASE_DIRT: 0,
    KIND_BASE_GRASS: 1,
    KIND_BASE_SAND: 2,
    KIND_BASE_ROCK: 3,
    KIND_BASE_ROAD: 4,
    KIND_BASE_CRACKED: 5,
    KIND_BASE_WATERBED: 6,

    # --- Детальные (накладываемые) слои ---
    KIND_OVERLAY_SNOW: 7,
    KIND_OVERLAY_LEAFS_GREEN: 8,
    KIND_OVERLAY_LEAFS_AUTUMN: 9,
    KIND_OVERLAY_FLOWERS: 10,
    KIND_OVERLAY_DIRT_GRASS: 11,
    KIND_OVERLAY_DESERT_STONES: 12,

    # ... здесь можно добавлять новые текстуры с ID до 31 ...
}

# --- Шаг 3: Автоматически создаем обратный словарь для удобства ---
SURFACE_ID_TO_KIND: Dict[int, str] = {
    v: k for k, v in SURFACE_KIND_TO_ID.items()
}

# --- Шаг 4: Создаем кортеж всех известных названий (для проверок) ---
SURFACE_KINDS: Tuple[str, ...] = tuple(SURFACE_KIND_TO_ID.keys())

# =======================================================================
# СЛОЙ 2: НАВИГАЦИЯ (NAVIGATION) - остается без изменений
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

# =======================================================================
# УТИЛИТЫ ДЛЯ РАБОТЫ С МАССИВАМИ
# =======================================================================
SURFACE_DTYPE = np.uint8
NAV_DTYPE = np.uint8


# --- Шаг 1: Создаем единую внутреннюю функцию для получения ID ---
def _get_id(kind_or_id: any, lookup_dict: Dict[str, int], default_id: int) -> int:
    """Внутренняя утилита: конвертирует строку в ID или возвращает ID как есть."""
    if isinstance(kind_or_id, int):
        return kind_or_id
    # Проверка на случай, если пришел numpy-тип
    if isinstance(kind_or_id, np.integer):
        return int(kind_or_id)
    return lookup_dict.get(kind_or_id, default_id)

# --- Шаг 2: Превращаем старые функции в простые и понятные обертки ---

def surface_fill(arr: np.ndarray, kind_or_id):
    """Заполняет массив указанным ID поверхности."""
    id_val = _get_id(kind_or_id, SURFACE_KIND_TO_ID, 0)
    arr.fill(id_val)

def surface_set(arr: np.ndarray, mask: np.ndarray, kind_or_id):
    """Устанавливает ID поверхности по маске."""
    id_val = _get_id(kind_or_id, SURFACE_KIND_TO_ID, 0)
    arr[mask] = id_val

def nav_fill(arr: np.ndarray, kind_or_id):
    """Заполняет массив указанным ID навигации."""
    id_val = _get_id(kind_or_id, NAV_KIND_TO_ID, 0)
    arr.fill(id_val)

def nav_set(arr: np.ndarray, mask: np.ndarray, kind_or_id):
    """Устанавливает ID навигации по маске."""
    id_val = _get_id(kind_or_id, NAV_KIND_TO_ID, 0)
    arr[mask] = id_val