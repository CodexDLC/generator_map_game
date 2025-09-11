# Файл: game_engine_restructured/world/features/blending.py
from __future__ import annotations
from .base_feature import FeatureBrush
from ...core import constants as const


class BlendingBrush(FeatureBrush):
    def apply(self, transition_width: int = 2):
        """
        Находит границы между разными базовыми текстурами и сглаживает их,
        добавляя переходную текстуру в overlay_grid.
        """
        print(f"  -> Applying blending brush for chunk ({self.result.cx}, {self.result.cz})...")
        h, w = self.size, self.size

        # ID переходной текстуры "земля-трава"
        dirt_grass_overlay_id = const.SURFACE_KIND_TO_ID.get(const.KIND_OVERLAY_DIRT_GRASS, 0)

        points_to_blend = []

        # Находим все точки на границе разных текстур
        for z in range(h):
            for x in range(w):
                current_type = self.surface_grid[z][x]
                for dz, dx in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                    nz, nx = z + dz, x + dx
                    if 0 <= nz < h and 0 <= nx < w:
                        neighbor_type = self.surface_grid[nz][nx]
                        if current_type != neighbor_type:
                            points_to_blend.append((x, z))
                            break

        # "Рисуем" переходной текстурой вокруг найденных точек
        for x, z in points_to_blend:
            for dz in range(-transition_width, transition_width + 1):
                for dx in range(-transition_width, transition_width + 1):
                    nz, nx = z + dz, x + dx
                    if 0 <= nz < h and 0 <= nx < w:
                        # Применяем только к траве или земле, чтобы не закрасить скалы
                        if self.surface_grid[nz][nx] in (const.KIND_BASE_GRASS, const.KIND_BASE_DIRT):
                            self.overlay_grid[nz][nx] = dirt_grass_overlay_id