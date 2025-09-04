from __future__ import annotations
from typing import List, Tuple, Optional

from .a_star import find_path as astar_find
from .policies import PathPolicy, ROAD_POLICY, NAV_POLICY, make_road_policy

# --- НАЧАЛО ИЗМЕНЕНИЯ: Убираем дубликат, импортируем из helpers ---
from .helpers import Coord
# --- КОНЕЦ ИЗМЕНЕНИЯ ---

class BaseRoadRouter:
    """
    Базовый «роутер» для ПРОКЛАДКИ ДОРОГ.
    По умолчанию: 4-соседей, без срезания углов, дорога дешевле, вода запрещена.
    """
    def __init__(self, policy: Optional[PathPolicy] = None):
        self.policy: PathPolicy = policy or ROAD_POLICY

    @classmethod
    def with_water(cls, water_cost: float = 25.0) -> "BaseRoadRouter":
        """Вариант, который разрешает пересекать воду с высокой ценой."""
        return cls(policy=make_road_policy(pass_water=True, water_cost=water_cost))

    def find(
        self,
        kind_grid: List[List[str]],
        height_grid: Optional[List[List[float]]],
        start: Coord,
        goal: Coord,
    ) -> List[Coord] | None:
        return astar_find(kind_grid, height_grid, start, goal, policy=self.policy)


class NavRouter(BaseRoadRouter):
    """
    Роутер для ПЕРСОНАЖА/ИИ.
    По умолчанию: 8-соседей, без срезания углов, вода/склоны/горы непроходимы,
    дорога дешевле.
    """
    def __init__(self, policy: Optional[PathPolicy] = None, slope_penalty: float = 0.08):
        if policy is None:
            policy = NAV_POLICY.with_overrides(slope_penalty_per_meter=slope_penalty)
        super().__init__(policy=policy)
