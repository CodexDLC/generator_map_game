from __future__ import annotations
import random
import math
from typing import List, Dict, Any

from .base_feature import FeatureBrush
from ...core.constants import KIND_GROUND, KIND_FOREST_GROUND, NAV_OBSTACLE
from ...world_structure.prefab_manager import PrefabManager
from ...core.grid.hex import HexGridSpec


@dataclass
class PlacedObject:
    prefab_id: str
    center_q: int
    center_r: int
    rotation: float
    scale: float = 1.0


class ObjectBrush(FeatureBrush):
    def __init__(self, result: GenResult, preset: Any, prefab_manager: PrefabManager, grid_spec: HexGridSpec):
        super().__init__(result, preset)
        self.prefab_manager = prefab_manager
        self.grid_spec = grid_spec
        # У этого чанка будет свой список размещенных объектов
        if not hasattr(self.result, 'placed_objects'):
            self.result.placed_objects: List[PlacedObject] = []

    def apply(self, density: float = 0.01, nav_buffer_m: float = 0.5):
        """Расставляет крупные объекты (деревья, скалы) из каталога."""

        rng = random.Random(self.result.stage_seeds.get("obstacles", self.result.seed))
        possible_points = []
        for r in range(self.size):
            for q in range(self.size):
                # Объекты можно ставить только на землю или лесную землю
                if self.surface_grid[r][q] in [KIND_GROUND, KIND_FOREST_GROUND]:
                    possible_points.append((q, r))

        rng.shuffle(possible_points)

        # Создаем временную маску, чтобы объекты не ставились друг на друга
        blocked_hexes = set()

        num_to_place = int(len(possible_points) * density)

        for q, r in possible_points:
            if not num_to_place: break
            if (q, r) in blocked_hexes: continue

            # Выбираем случайный префаб из каталога
            prefab_id = rng.choice(self.prefab_manager.get_all_ids())
            prefab = self.prefab_manager.get_prefab(prefab_id)
            if not prefab: continue

            # --- Расчет "следа" (Footprint) ---
            footprint = prefab.footprint
            # Полуоси эллипса с учетом буфера
            a = (footprint.width / 2) + nav_buffer_m
            b = (footprint.depth / 2) + nav_buffer_m

            # Примерный радиус поиска в гексах
            search_radius_m = max(a, b)
            # Узнаем, сколько метров в одном "шаге" по гексу
            hex_step_m = self.grid_spec.edge_m * 1.5
            search_radius_hex = math.ceil(search_radius_m / hex_step_m)

            hexes_to_block = set()

            # Проверяем все гексы в радиусе
            for dr in range(-search_radius_hex, search_radius_hex + 1):
                for dq in range(-search_radius_hex, search_radius_hex + 1):
                    # Проверяем расстояние, чтобы не сканировать лишнего
                    if self.grid_spec.cube_distance(0, 0, dq, dr) > search_radius_hex:
                        continue

                    check_q, check_r = q + dq, r + dr

                    # Получаем мировые координаты центра проверяемого гекса
                    center_wx, center_wz = self.grid_spec.axial_to_world(q, r)
                    check_wx, check_wz = self.grid_spec.axial_to_world(check_q, check_r)

                    # Простой тест на попадание в эллипс
                    if ((check_wx - center_wx) ** 2 / a ** 2 + (check_wz - center_wz) ** 2 / b ** 2) <= 1:
                        hexes_to_block.add((check_q, check_r))

            # --- Применение ---
            # Добавляем объект в список и блокируем гексы
            rotation = rng.uniform(0, 360)
            self.result.placed_objects.append(PlacedObject(prefab_id, q, r, rotation))

            for bq, br in hexes_to_block:
                # Проверяем, что координаты внутри текущего чанка
                # (для простоты пока не ставим объекты на границах)
                if 0 <= bq < self.size and 0 <= br < self.size:
                    self.nav_grid[br][bq] = NAV_OBSTACLE
                    blocked_hexes.add((bq, br))

            num_to_place -= 1

        print(
            f"--- OBJECT BRUSH: Placed {len(self.result.placed_objects)} objects in chunk ({self.result.cx}, {self.result.cz})")