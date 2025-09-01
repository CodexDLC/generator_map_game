from __future__ import annotations
from dataclasses import dataclass, replace
from typing import Callable, Dict, Tuple

from .helpers import (
    Coord, NEI4, NEI8,
    DEFAULT_TERRAIN_FACTOR,
    heuristic_l1, heuristic_octile,
)

# Пытаемся взять константы типов (для явного редактирования стоимости воды и т.п.)
try:
    from engine.worldgen_core.base.constants import (
        KIND_GROUND, KIND_OBSTACLE, KIND_WATER, KIND_ROAD, KIND_VOID, KIND_SLOPE
    )
except Exception:
    KIND_GROUND = "ground"
    KIND_OBSTACLE = "obstacle"
    KIND_WATER = "water"
    KIND_ROAD = "road"
    KIND_VOID = "void"
    KIND_SLOPE = "slope"


@dataclass(frozen=True)
class PathPolicy:
    """Профиль поиска пути (и для дорог, и для ИИ)."""
    neighbors: Tuple[Coord, ...]                     # набор соседей (4/8)
    corner_cut: bool                                 # разрешать «резать углы» по диагонали
    terrain_factor: Dict[str, float]                 # стоимость входа в клетку по типу
    slope_penalty_per_meter: float                   # штраф за |Δh| между клетками (в метрах)
    heuristic: Callable[[Coord, Coord], float]       # функция эвристики

    def with_overrides(self, **kwargs) -> "PathPolicy":
        """Клонирование с частичной заменой полей."""
        return replace(self, **kwargs)


# --------- Фабрики политик ---------

def make_road_policy(
    pass_water: bool = False,
    water_cost: float = 25.0,
    slope_penalty: float = 0.4,
) -> PathPolicy:
    """
    Политика для генерации дорог:
      - 4-соседей, без «срезания углов»
      - дорога дешевле, склоны/горы непроходимы
      - воду можно разрешить (дорого) или запретить
      - эвристика L1 (манхэттен)
    """
    tf = dict(DEFAULT_TERRAIN_FACTOR)
    # Уточняем типы
    tf[KIND_ROAD] = 0.7
    tf[KIND_OBSTACLE] = float("inf")
    tf[KIND_SLOPE] = float("inf")
    tf[KIND_VOID] = float("inf")
    tf[KIND_WATER] = (water_cost if pass_water else float("inf"))

    return PathPolicy(
        neighbors=NEI4,
        corner_cut=False,
        terrain_factor=tf,
        slope_penalty_per_meter=slope_penalty,
        heuristic=heuristic_l1,
    )


def make_nav_policy(
    slope_penalty: float = 0.08,
) -> PathPolicy:
    """
    Политика для ИИ/персонажа:
      - 8-соседей, без «срезания углов»
      - вода/горы/склоны непроходимы
      - дорога чуть дешевле
      - эвристика octile
    """
    tf = dict(DEFAULT_TERRAIN_FACTOR)
    tf[KIND_ROAD] = 0.6
    tf[KIND_OBSTACLE] = float("inf")
    tf[KIND_SLOPE] = float("inf")
    tf[KIND_WATER] = float("inf")
    tf[KIND_VOID] = float("inf")

    return PathPolicy(
        neighbors=NEI8,
        corner_cut=False,                 # диагональ разрешена, но без прорезания углов
        terrain_factor=tf,
        slope_penalty_per_meter=slope_penalty,
        heuristic=heuristic_octile,
    )


# --------- Готовые профили по умолчанию ---------

ROAD_POLICY: PathPolicy = make_road_policy(pass_water=False)
NAV_POLICY: PathPolicy  = make_nav_policy()
