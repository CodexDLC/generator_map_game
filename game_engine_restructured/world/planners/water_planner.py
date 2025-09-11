from __future__ import annotations
from typing import TYPE_CHECKING
import numpy as np
import random
import math
from opensimplex import OpenSimplex

# ИЗМЕНЕНИЕ: Удалены импорты, которые не используются в этих функциях
# from ...core import constants as const
# from ..grid_utils import _stitch_layers, _apply_changes_to_chunks

if TYPE_CHECKING:
    from ...core.preset.model import Preset
    from ...core.types import GenResult


def _generate_lakes_on_stitched_map(stitched_heights: np.ndarray, preset: Preset, seed: int):
    """Генерирует озера прямо на большой карте высот региона."""
    water_cfg = preset.water
    if not water_cfg or not water_cfg.get("enabled"): return

    rng = random.Random(seed)
    num_lakes_to_try = (preset.region_size ** 2) // 2

    for _ in range(num_lakes_to_try):
        if rng.random() > water_cfg.get("lake_chance_base", 0.1): continue

        size = stitched_heights.shape[0]
        min_radius = water_cfg.get("lake_min_radius", 15)
        max_radius = water_cfg.get("lake_max_radius", 50)
        radius = rng.randint(min_radius, max_radius)

        border = radius + 32  # Безопасная зона
        center_x = rng.randint(border, size - border)
        center_z = rng.randint(border, size - border)

        z_coords, x_coords = np.ogrid[:size, :size]
        dist_sq = (x_coords - center_x) ** 2 + (z_coords - center_z) ** 2
        lake_mask = dist_sq < radius ** 2

        if not np.any(lake_mask): continue

        shore_heights = stitched_heights[lake_mask]
        if shore_heights.size == 0: continue

        avg_shore_height = np.mean(shore_heights)
        flatten_depth = water_cfg.get("lake_flatten_depth_m", -5.0)
        target_height = avg_shore_height + flatten_depth

        stitched_heights[lake_mask] = target_height

def _generate_rivers_on_stitched_map(stitched_heights: np.ndarray, preset: Preset, seed: int):
    """
    TODO: Здесь будет логика генерации рек.
    """
    pass