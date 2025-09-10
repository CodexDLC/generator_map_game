# game_engine/story_features/features/rocks.py
from __future__ import annotations
from opensimplex import OpenSimplex

from ...core.constants import KIND_GROUND, KIND_SAND, KIND_SLOPE, NAV_OBSTACLE
from .base_feature import FeatureBrush


class RockBrush(FeatureBrush):
    def apply(
        self, density: float = 0.05, near_slope_multiplier: float = 5.0, **kwargs
    ):
        """
        Применяет "кисть" для генерации камней.
        Теперь работает с двумя слоями: surface и navigation.
        """
        rock_noise_gen = OpenSimplex((self.result.seed ^ 0xDEADBEEF) & 0x7FFFFFFF)
        rock_count = 0

        for z in range(self.size):
            for x in range(self.size):
                # --- ИЗМЕНЕНИЕ: Проверяем СЛОЙ ПОВЕРХНОСТЕЙ ---
                # Камни могут появляться только на земле или песке
                if self.surface_grid[z][x] in (KIND_GROUND, KIND_SAND):
                    is_near_slope = False
                    for dz in range(-1, 2):
                        for dx in range(-1, 2):
                            if dx == 0 and dz == 0:
                                continue
                            nx, nz = x + dx, z + dz
                            # --- ИЗМЕНЕНИЕ: Проверяем СЛОЙ ПОВЕРХНОСТЕЙ на наличие склона ---
                            if (
                                0 <= nx < self.size
                                and 0 <= nz < self.size
                                and self.surface_grid[nz][nx] == KIND_SLOPE
                            ):
                                is_near_slope = True
                                break
                        if is_near_slope:
                            break

                    chance_multiplier = near_slope_multiplier if is_near_slope else 1.0
                    noise_val = (rock_noise_gen.noise2(x * 0.5, z * 0.5) + 1.0) / 2.0

                    if noise_val < (density * chance_multiplier):
                        # --- ИЗМЕНЕНИЕ: Применяем изменения к двум слоям ---
                        # 1. Поверхность меняем на "склон" (каменистая текстура)
                        self.surface_grid[z][x] = KIND_SLOPE
                        # 2. Ставим в навигационной сетке маркер непроходимого объекта
                        self.nav_grid[z][x] = NAV_OBSTACLE
                        rock_count += 1

        if rock_count > 0:
            print(
                f"--- ROCK BRUSH: Painted {rock_count} rocks for chunk ({self.result.cx}, {self.result.cz})"
            )
