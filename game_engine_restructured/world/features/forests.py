# game_engine/world/features/forests.py
from __future__ import annotations
import random
from opensimplex import OpenSimplex

from .base_feature import FeatureBrush

# --- ИЗМЕНЕНИЕ: Импортируем модуль констант ---
from ...core import constants as const


class ForestBrush(FeatureBrush):
    def apply(self, tree_rock_ratio: float = 0.95, min_distance: int = 2, **kwargs):
        """
        Применяет "кисть" для генерации леса:
        1. Создает "пятно" леса на основе шума.
        2. Внутри пятна меняет базовую текстуру и добавляет слой листьев.
        3. Расставляет внутри деревья и камни как непроходимые объекты.
        """
        cfg = getattr(self.preset, "scatter", {})
        if not cfg.get("enabled", False):
            return

        # --- ЭТАП 1: Создание маски леса (остаётся без изменений) ---
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

        # Лес может расти только на траве
        allowed_base_surfaces = (const.KIND_BASE_GRASS,)

        for z in range(self.size):
            for x in range(self.size):
                if self.surface_grid[z][x] in allowed_base_surfaces:
                    wx = self.result.cx * self.size + x
                    wz = self.result.cz * self.size + z
                    group_val = (
                        group_noise_gen.noise2(wx * group_freq, wz * group_freq) + 1.0
                    ) / 2.0
                    if group_val > group_threshold:
                        detail_val = (
                            detail_noise_gen.noise2(wx * detail_freq, wz * detail_freq)
                            + 1.0
                        ) / 2.0
                        if detail_val > detail_threshold:
                            scatter_mask[z][x] = True

        # --- ЭТАП 2: Раскрашиваем область леса и добавляем детальные слои ---
        possible_points = []
        leaf_overlay_id = const.SURFACE_KIND_TO_ID.get(
            const.KIND_OVERLAY_LEAFS_GREEN, 0
        )

        for z in range(self.size):
            for x in range(self.size):
                if scatter_mask[z][x]:
                    # Меняем базовый слой на землю
                    self.surface_grid[z][x] = const.KIND_BASE_DIRT
                    # Добавляем ID слоя с листьями в overlay_grid
                    self.overlay_grid[z][x] = leaf_overlay_id
                    possible_points.append((x, z))

        # --- ЭТАП 3: Прореживаем и расставляем НЕПРОХОДИМЫЕ объекты (без изменений) ---
        rng = random.Random(self.result.stage_seeds.get("obstacles", self.result.seed))
        rng.shuffle(possible_points)
        placement_forbidden = [
            [False for _ in range(self.size)] for _ in range(self.size)
        ]
        tree_count = 0
        rock_count = 0

        for x, z in possible_points:
            if placement_forbidden[z][x]:
                continue

            # Ставим либо дерево, либо камень как препятствие
            if rng.random() < tree_rock_ratio:
                self.nav_grid[z][x] = const.NAV_OBSTACLE
                tree_count += 1
            else:
                self.nav_grid[z][x] = const.NAV_OBSTACLE
                self.surface_grid[z][x] = const.KIND_BASE_ROCK
                # Убираем листья из-под камня
                self.overlay_grid[z][x] = 0
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
                f"--- FOREST BRUSH: Painted forest area and placed {tree_count} trees, {rock_count} rocks."
            )
