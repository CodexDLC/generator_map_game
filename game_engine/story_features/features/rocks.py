# game_engine/story_features/features/rocks.py
from __future__ import annotations
from opensimplex import OpenSimplex

from ...core.constants import KIND_GROUND, KIND_SAND, KIND_ROCK, KIND_SLOPE
from .base_feature import FeatureBrush


class RockBrush(FeatureBrush):
    def apply(self, density: float = 0.05, near_slope_multiplier: float = 5.0, **kwargs):
        """
        Применяет "кисть" для генерации камней.

        :param density: Базовая плотность камней на ровной местности.
        :param near_slope_multiplier: Во сколько раз увеличивается шанс появления камня рядом со склоном.
        """
        # Свой собственный, независимый генератор шума для камней
        rock_noise_gen = OpenSimplex((self.result.seed ^ 0xDEADBEEF) & 0x7FFFFFFF)
        rock_count = 0

        for z in range(self.size):
            for x in range(self.size):
                # Камни могут появляться только на земле или песке, и там, где еще ничего не выросло
                if self.kind_grid[z][x] in (KIND_GROUND, KIND_SAND):
                    is_near_slope = False

                    # Проверяем 8 соседей на наличие склона
                    for dz in range(-1, 2):
                        for dx in range(-1, 2):
                            if dx == 0 and dz == 0: continue
                            nx, nz = x + dx, z + dz
                            if 0 <= nx < self.size and 0 <= nz < self.size and self.kind_grid[nz][nx] == KIND_SLOPE:
                                is_near_slope = True
                                break
                        if is_near_slope: break

                    # Если рядом есть склон, шанс появления камня сильно повышается
                    chance_multiplier = near_slope_multiplier if is_near_slope else 1.0

                    # Используем простой шум для случайности
                    noise_val = (rock_noise_gen.noise2(x * 0.5, z * 0.5) + 1.0) / 2.0

                    if noise_val < (density * chance_multiplier):
                        self.kind_grid[z][x] = KIND_ROCK
                        rock_count += 1

        if rock_count > 0:
            print(f"--- ROCK BRUSH: Painted {rock_count} rocks for chunk ({self.result.cx}, {self.result.cz})")