# game_engine/algorithms/pathfinding/policies.py
from __future__ import annotations
from dataclasses import dataclass, replace
from typing import Callable, Dict, Tuple

# --- Импорты (без изменений) ---
from .helpers import (
    Coord, NEI4, NEI8,
    heuristic_l1, heuristic_octile,
)
from ...core.constants import (
    DEFAULT_TERRAIN_FACTOR, KIND_ROAD, KIND_OBSTACLE,
    KIND_SLOPE, KIND_VOID, KIND_WATER
)


@dataclass(frozen=True)
class PathPolicy:
    """Профиль поиска пути (и для дорог, и для ИИ)."""
    neighbors: Tuple[Coord, ...]
    corner_cut: bool
    terrain_factor: Dict[str, float]
    slope_penalty_per_meter: float
    heuristic: Callable[[Coord, Coord], float]

    def with_overrides(self, **kwargs) -> "PathPolicy":
        """Клонирование с частичной заменой полей."""
        return replace(self, **kwargs)


# --------- Фабрики политик ---------

def make_road_policy(
        allow_slopes: bool = False,  # <-- Новый параметр
        slope_cost: float = 5.0,  # <-- Новый параметр
        pass_water: bool = False,
        water_cost: float = 25.0,
        slope_penalty: float = 0.4,
) -> PathPolicy:
    """Универсальная политика для генерации дорог."""
    tf = dict(DEFAULT_TERRAIN_FACTOR)
    tf[KIND_ROAD] = 0.7
    tf[KIND_OBSTACLE] = float("inf")
    tf[KIND_VOID] = float("inf")

    # Управляем проходимостью склонов и воды через параметры
    tf[KIND_SLOPE] = slope_cost if allow_slopes else float("inf")
    tf[KIND_WATER] = water_cost if pass_water else float("inf")

    return PathPolicy(
        neighbors=NEI8,
        corner_cut=False,
        terrain_factor=tf,
        slope_penalty_per_meter=slope_penalty,
        heuristic=heuristic_octile,
    )

def make_nav_policy(
    slope_penalty: float = 0.08,
) -> PathPolicy:
    """Политика для ИИ/персонажа."""
    tf = dict(DEFAULT_TERRAIN_FACTOR)
    tf[KIND_ROAD] = 0.6
    tf[KIND_OBSTACLE] = float("inf")
    tf[KIND_SLOPE] = float("inf")
    tf[KIND_WATER] = float("inf")
    tf[KIND_VOID] = float("inf")

    return PathPolicy(
        neighbors=NEI8,
        corner_cut=False,
        terrain_factor=tf,
        slope_penalty_per_meter=slope_penalty,
        heuristic=heuristic_octile,
    )


# --------- Готовые профили по умолчанию ---------

ROAD_POLICY: PathPolicy = make_road_policy(pass_water=False)
NAV_POLICY: PathPolicy  = make_nav_policy()