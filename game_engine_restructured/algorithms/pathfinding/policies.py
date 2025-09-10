# game_engine/algorithms/pathfinding/policies.py
from __future__ import annotations
from dataclasses import dataclass, replace
from typing import Callable, Dict, List

from ...core import constants as const
# --- ИЗМЕНЕНИЕ: Теперь импортируем все нужное из helpers ---
from .helpers import (
    Coord,
    NEI6_AXIAL,
    heuristic_hex,
    DEFAULT_TERRAIN_FACTOR
)


@dataclass(frozen=True)
class PathPolicy:
    grid_type: str
    neighbors: List[Coord]
    terrain_factor: Dict[str, float]
    nav_factor: Dict[str, float]
    slope_penalty_per_meter: float
    heuristic: Callable[[Coord, Coord], float]

    def with_overrides(self, **kwargs) -> "PathPolicy":
        return replace(self, **kwargs)


def make_base_policy() -> PathPolicy:
    """Создает базовую политику для гексагональной сетки."""
    nav_factor = {
        const.NAV_PASSABLE: 1.0,
        const.NAV_OBSTACLE: float("inf"),
        const.NAV_WATER: float("inf"),
        const.NAV_BRIDGE: 1.0,
    }
    return PathPolicy(
        grid_type="hex",
        neighbors=NEI6_AXIAL,
        terrain_factor=DEFAULT_TERRAIN_FACTOR.copy(),
        nav_factor=nav_factor,
        slope_penalty_per_meter=0.1,
        heuristic=heuristic_hex,
    )


def make_road_policy(
        allow_slopes: bool = True,
        slope_cost: float = 5.0,
        allow_water_as_bridge: bool = True,
        water_bridge_cost: float = 15.0,
) -> PathPolicy:
    """Политика для ГЕНЕРАЦИИ ДОРОГ."""
    policy = make_base_policy()

    # Используем одну и ту же стоимость для разных дорог
    policy.terrain_factor[const.KIND_BASE_DIRT] = 0.5
    policy.terrain_factor[const.KIND_ROAD_PAVED] = 0.5

    if allow_slopes:
        policy.terrain_factor[const.KIND_BASE_ROCK] = slope_cost
    else:
        policy.terrain_factor[const.KIND_BASE_ROCK] = float("inf")

    if allow_water_as_bridge:
        policy.nav_factor[const.NAV_WATER] = water_bridge_cost

    return policy


def make_nav_policy() -> PathPolicy:
    """Политика для ПЕРСОНАЖА/ИИ."""
    policy = make_base_policy()

    policy.terrain_factor[const.KIND_BASE_DIRT] = 0.8
    policy.terrain_factor[const.KIND_ROAD_PAVED] = 0.6
    policy.terrain_factor[const.KIND_BASE_ROCK] = float("inf")

    return policy


# Готовые профили по умолчанию
ROAD_POLICY: PathPolicy = make_road_policy()
NAV_POLICY: PathPolicy = make_nav_policy()