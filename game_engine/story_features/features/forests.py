# game_engine/story_features/features/forests.py
from __future__ import annotations
import random
from opensimplex import OpenSimplex


from .base_feature import FeatureBrush
from ...core.constants import KIND_GROUND, KIND_SAND, KIND_TREE, KIND_ROCK


class ForestBrush(FeatureBrush):
    def apply(self, tree_rock_ratio: float = 0.95, min_distance: int = 2, **kwargs):
        """
        Применяет "кисть" для генерации леса.

        :param tree_rock_ratio: Вероятность того, что объект будет деревом (остальное - камень).
        :param min_distance: Минимальное расстояние в клетках между объектами.
        """
        cfg = getattr(self.preset, "scatter", {})
        if not cfg.get("enabled", False): return

        # --- ЭТАП 1: Создание сплошных "пятен" (маски) ---
        groups_cfg = cfg.get("groups", {})
        details_cfg = cfg.get("details", {})

        group_scale = float(groups_cfg.get("noise_scale_tiles", 64.0))
        group_threshold = float(groups_cfg.get("threshold", 0.45))
        group_freq = 1.0 / group_scale

        detail_scale = float(details_cfg.get("noise_scale_tiles", 7.0))
        detail_threshold = float(details_cfg.get("threshold", 0.55))
        detail_freq = 1.0 / detail_scale

        group_noise_gen = OpenSimplex((self.result.seed ^ 0xABCDEFAB) & 0x7FFFFFFF)
        detail_noise_gen = OpenSimplex((self.result.seed ^ 0x12345678) & 0x7FFFFFFF)

        scatter_mask = [[False for _ in range(self.size)] for _ in range(self.size)]
        for z in range(self.size):
            for x in range(self.size):
                if self.kind_grid[z][x] in (KIND_GROUND, KIND_SAND):
                    wx = self.result.cx * self.size + x
                    wz = self.result.cz * self.size + z
                    group_val = (group_noise_gen.noise2(wx * group_freq, wz * group_freq) + 1.0) / 2.0
                    if group_val > group_threshold:
                        detail_val = (detail_noise_gen.noise2(wx * detail_freq, wz * detail_freq) + 1.0) / 2.0
                        if detail_val > detail_threshold:
                            scatter_mask[z][x] = True

        # --- ЭТАП 2: Прореживание маски по алгоритму "случайный отбор с защитной зоной" ---
        possible_points = []
        for z in range(self.size):
            for x in range(self.size):
                if scatter_mask[z][x]:
                    possible_points.append((x, z))

        rng = random.Random(self.result.stage_seeds.get("obstacles", self.result.seed))
        rng.shuffle(possible_points)

        placement_forbidden = [[False for _ in range(self.size)] for _ in range(self.size)]
        tree_count = 0
        rock_count = 0

        for x, z in possible_points:
            if placement_forbidden[z][x]:
                continue

            # Выбираем, что поставить: дерево или камень
            if rng.random() < tree_rock_ratio:
                self.kind_grid[z][x] = KIND_TREE
                tree_count += 1
            else:
                # Камни ставим, только если клетка все еще свободна
                if self.kind_grid[z][x] not in (KIND_TREE, KIND_ROCK):
                    self.kind_grid[z][x] = KIND_ROCK
                    rock_count += 1

            # Блокируем "защитную зону" вокруг нового объекта
            for dz in range(-min_distance, min_distance + 1):
                for dx in range(-min_distance, min_distance + 1):
                    nx, nz = x + dx, z + dz
                    if 0 <= nx < self.size and 0 <= nz < self.size:
                        placement_forbidden[nz][nx] = True

        total = tree_count + rock_count
        if total > 0:
            print(
                f"--- FOREST BRUSH: Painted {tree_count} trees and {rock_count} rocks for chunk ({self.result.cx}, {self.result.cz})")