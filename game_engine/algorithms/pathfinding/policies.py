# game_engine/algorithms/pathfinding/policies.py
from __future__ import annotations
from dataclasses import dataclass, replace
from typing import Callable, Dict, Tuple

from .helpers import (
    Coord, NEI8,
    heuristic_octile,
)
# --- ИЗМЕНЕНИЕ: Импортируем новые константы ---
from ...core.constants import (
    DEFAULT_TERRAIN_FACTOR, NAV_OBSTACLE, NAV_WATER, NAV_BRIDGE
)


@dataclass(frozen=True)
class PathPolicy:
    """Профиль поиска пути (и для дорог, и для ИИ)."""
    neighbors: Tuple[Coord, ...]
    corner_cut: bool
    terrain_factor: Dict[str, float]  # Стоимость движения по ПОВЕРХНОСТИ
    nav_factor: Dict[str, float]  # Стоимость движения по НАВИГАЦИОННОЙ сетке
    slope_penalty_per_meter: float
    heuristic: Callable[[Coord, Coord], float]

    def with_overrides(self, **kwargs) -> "PathPolicy":
        return replace(self, **kwargs)


def make_base_policy() -> PathPolicy:
    """Создает базовую политику с общими настройками."""
    # Стоимость в nav_grid: ходить можно везде, кроме препятствий и воды. По мосту можно.
    nav_factor = {
        "passable": 1.0,
        "obstacle_prop": float("inf"),
        "water": float("inf"),
        "bridge": 1.0,  # Мост проходим
    }
    return PathPolicy(
        neighbors=NEI8,
        corner_cut=False,
        terrain_factor=DEFAULT_TERRAIN_FACTOR.copy(),
        nav_factor=nav_factor,
        slope_penalty_per_meter=0.1,
        heuristic=heuristic_octile,
    )


def make_road_policy(
        allow_slopes: bool = True,
        slope_cost: float = 5.0,
        allow_water_as_bridge: bool = True,
        water_bridge_cost: float = 15.0,
) -> PathPolicy:
    """Политика для ГЕНЕРАЦИИ ДОРОГ."""
    policy = make_base_policy()

    # Дороги предпочитают строиться по уже существующим дорогам
    policy.terrain_factor["road"] = 0.5
    # Склоны для дорог очень дорогие, но возможны
    if allow_slopes:
        policy.terrain_factor["slope"] = slope_cost
    else:
        policy.terrain_factor["slope"] = float("inf")

    # Разрешаем строить "мосты" (логические) через воду
    if allow_water_as_bridge:
        policy.nav_factor["water"] = water_bridge_cost

    return policy


def make_nav_policy() -> PathPolicy:
    """Политика для ПЕРСОНАЖА/ИИ."""
    policy = make_base_policy()
    # Персонаж предпочитает дороги
    policy.terrain_factor["road"] = 0.6
    # Но по склонам ходить не умеет
    policy.terrain_factor["slope"] = float("inf")

    return policy


# Готовые профили по умолчанию
ROAD_POLICY: PathPolicy = make_road_policy()
NAV_POLICY: PathPolicy = make_nav_policy()