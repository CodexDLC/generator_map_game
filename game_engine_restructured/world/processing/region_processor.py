# Файл: game_engine_restructured/world/processing/region_processor.py
from __future__ import annotations
from typing import Dict, Tuple
import numpy as np

from ...core import constants as const
from ...core.preset import Preset
from ...core.types import GenResult
from ..grid_utils import _stitch_layers, _apply_changes_to_chunks
from ...algorithms.climate.climate import generate_climate_maps, apply_biomes_to_surface
from ...algorithms.terrain.terrain import apply_slope_obstacles
from ..planners.water_planner import _generate_lakes_on_stitched_map, _generate_rivers_on_stitched_map


class RegionProcessor:
    def __init__(self, preset: Preset, world_seed: int):
        self.preset = preset
        self.world_seed = world_seed

    def process(self, scx: int, scz: int, base_chunks: Dict[Tuple[int, int], GenResult]) -> Dict[
        Tuple[int, int], GenResult]:
        print(f"[RegionProcessor] STARTING for region ({scx}, {scz})...")

        first_chunk = next(iter(base_chunks.values()))
        chunk_size = first_chunk.size
        region_size = int(self.preset.region_size)
        region_seed = self.world_seed ^ (scx * 100 + scz)

        # ЭТАП 1: ГЕНЕРАЦИЯ И СШИВАНИЕ СЫРЫХ ДАННЫХ
        # У нас нет elevation_grid_with_margin, поэтому временно будем работать без него.
        # В идеале нужно переработать BaseProcessor, чтобы он возвращал его напрямую.
        stitched_layers, (base_cx, base_cz) = _stitch_layers(region_size, chunk_size, base_chunks, ['height'])
        stitched_heights = stitched_layers['height']

        # ЭТАП 2: РЕГИОНАЛЬНАЯ ОБРАБОТКА (СЛОНЫ, ГИДРОЛОГИЯ, КЛИМАТ)
        # ИЗМЕНЕНИЕ: Применяем склоны к сшитой карте
        apply_slope_obstacles(stitched_heights, stitched_layers['surface'], self.preset)

        # Применяем логику озер и рек к общей карте высот
        _generate_lakes_on_stitched_map(stitched_heights, self.preset, region_seed)
        _generate_rivers_on_stitched_map(stitched_heights, self.preset, region_seed)

        # Наносим базовый уровень моря на сшитую карту
        sea_level = self.preset.elevation.get("sea_level_m", 0.0)
        water_mask = stitched_heights <= sea_level
        stitched_surface = np.full(stitched_heights.shape, const.KIND_BASE_DIRT, dtype=object)
        stitched_nav = np.full(stitched_heights.shape, const.NAV_PASSABLE, dtype=object)
        stitched_surface[water_mask] = const.KIND_BASE_SAND
        stitched_nav[water_mask] = const.NAV_WATER
        stitched_layers['surface'] = stitched_surface
        stitched_layers['navigation'] = stitched_nav

        # ЭТАП 3: КЛИМАТ И БИОМЫ
        # TODO: Здесь мы будем генерировать климат, используя сшитые высоты и воду
        # Это будет работать так: generate_climate_maps(stitched_layers, self.preset)

        # ЭТАП 4: НАРЕЗАЕМ ИЗМЕНЕННУЮ КАРТУ ОБРАТНО НА ЧАНКИ
        _apply_changes_to_chunks(stitched_layers, base_chunks, base_cx, base_cz, chunk_size)

        # ЭТАП 5: ОСТАЛЬНАЯ ПОЧАНКОВАЯ ОБРАБОТКА (БИОМЫ И ДР.)
        # Теперь все слои в чанках уже обновлены, поэтому мы можем просто итерировать
        # и применять биомы, так как они работают по чанково.
        for chunk in base_chunks.values():
            apply_biomes_to_surface(chunk)
            # УДАЛЕНО: Устаревший вызов apply_slope_obstacles, который вызывал ошибку.

        print(f"[RegionProcessor] FINISHED for region ({scx}, {scz}).")
        return base_chunks