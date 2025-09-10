# Файл: game_engine_restructured/world/processing/region_processor.py
from __future__ import annotations
from typing import Dict, Tuple
import numpy as np

from ...core import constants as const
from ...core.preset import Preset
from ...core.types import GenResult
from ..planners.water_planner import _stitch_layers, _apply_changes_to_chunks
from ...algorithms.climate.climate import generate_climate_maps, apply_biomes_to_surface
from ...algorithms.terrain.terrain import apply_slope_obstacles


class RegionProcessor:
    def __init__(self, preset: Preset):
        self.preset = preset

    def process(self, scx: int, scz: int, base_chunks: Dict[Tuple[int, int], GenResult]) -> Dict[
        Tuple[int, int], GenResult]:
        print(f"[RegionProcessor] STARTING for region ({scx}, {scz})...")

        region_size = self.preset.region_size
        chunk_size = self.preset.size

        # --- ЭТАП 1: Склеиваем карты высот ---
        stitched_layers, (base_cx, base_cz) = _stitch_layers(region_size, chunk_size, base_chunks, ['height'])
        stitched_heights = stitched_layers['height']

        # --- ЭТАП 2: Определяем зоны воды по ГЛОБАЛЬНОМУ УРОВНЮ МОРЯ ---
        # ВАЖНО: Мы больше НЕ вычитаем sea_level из stitched_heights!
        sea_level = self.preset.elevation.get("sea_level_m", 0.0)
        water_mask = stitched_heights <= sea_level
        print(f"-> Using sea level: {sea_level}m to determine water areas.")

        # --- ЭТАП 3: Создаем слои поверхности и навигации ---
        stitched_surface = np.full(stitched_heights.shape, const.KIND_BASE_DIRT, dtype=object)
        stitched_surface[water_mask] = const.KIND_BASE_SAND  # Дно и пляжи - песок

        stitched_nav = np.full(stitched_heights.shape, const.NAV_PASSABLE, dtype=object)
        stitched_nav[water_mask] = const.NAV_WATER

        # --- ЭТАП 4: "Нарезаем" базовые слои обратно в чанки ---
        initial_layers = {'height': stitched_heights, 'surface': stitched_surface, 'navigation': stitched_nav}
        _apply_changes_to_chunks(initial_layers, base_chunks, base_cx, base_cz, chunk_size)

        # --- ЭТАП 5: Применяем климат и биомы (теперь они будут знать о воде) ---
        for chunk in base_chunks.values():
            generate_climate_maps(chunk, self.preset)
            apply_biomes_to_surface(chunk)

        # --- ЭТАП 6: Скалы на склонах ---
        for chunk in base_chunks.values():
            if "elevation_with_margin" in chunk.temp_data:
                # Расчет склонов ведется по оригинальным высотам, это правильно
                elevation_with_margin = chunk.temp_data["elevation_with_margin"]
                apply_slope_obstacles(elevation_with_margin, chunk.layers["surface"], self.preset)

        print(f"[RegionProcessor] FINISHED for region ({scx}, {scz}).")
        return base_chunks