# Файл: game_engine_restructured/world/processing/region_processor.py
from __future__ import annotations
from typing import Dict, Tuple
import numpy as np
from pathlib import Path

from ...core import constants as const
from ...core.preset import Preset
from ...core.types import GenResult
from ..grid_utils import _stitch_layers, _apply_changes_to_chunks, region_base
from ...algorithms.climate.climate import generate_climate_maps, apply_biomes_to_surface
from ...algorithms.terrain.terrain import apply_slope_obstacles
from ..planners.water_planner import _generate_lakes_on_stitched_map, _generate_rivers_on_stitched_map
from ...core.export import write_raw_json_grid


class RegionProcessor:
    def __init__(self, preset: Preset, world_seed: int, artifacts_root: Path):
        self.preset = preset
        self.world_seed = world_seed
        self.artifacts_root = artifacts_root # <--- ДОБАВЛЕНО

    def process(self, scx: int, scz: int, base_chunks: Dict[Tuple[int, int], GenResult]) -> Dict[
        Tuple[int, int], GenResult]:
        print(f"[RegionProcessor] STARTING for region ({scx}, {scz})...")

        first_chunk = next(iter(base_chunks.values()))
        chunk_size = first_chunk.size
        region_size = int(self.preset.region_size)
        region_seed = self.world_seed ^ (scx * 100 + scz)

        region_pixel_size = region_size * chunk_size
        base_cx, base_cz = region_base(scx, scz, region_size)

        # ЭТАП 1: ГЕНЕРАЦИЯ И СШИВАНИЕ СЫРЫХ ДАННЫХ
        stitched_layers, _ = _stitch_layers(region_size, chunk_size, base_chunks,
                                            ['height', 'surface', 'navigation'])

        # ЭТАП 2: РЕГИОНАЛЬНАЯ ОБРАБОТКА (СЛОНЫ, ГИДРОЛОГИЯ, КЛИМАТ)
        apply_slope_obstacles(stitched_layers['height'], stitched_layers['surface'], self.preset)
        _generate_lakes_on_stitched_map(stitched_layers['height'], self.preset, region_seed)
        _generate_rivers_on_stitched_map(stitched_layers['height'], self.preset, region_seed)

        # Наносим базовый уровень моря на сшитую карту
        sea_level = self.preset.elevation.get("sea_level_m", 0.0)
        water_mask = stitched_layers['height'] <= sea_level
        stitched_layers['surface'][water_mask] = const.KIND_BASE_SAND
        stitched_layers['navigation'][water_mask] = const.NAV_WATER

        # ЭТАП 3: КЛИМАТ И БИОМЫ
        generate_climate_maps(
            stitched_layers,
            self.preset,
            region_seed,
            base_cx,
            base_cz,
            region_pixel_size,
            region_size
        )

        # СОХРАНЯЕМ СЛОИ ДЛЯ ОТЛАДКИ В RAW ПАПКУ
        region_raw_path = self.artifacts_root / "world_raw" / str(self.world_seed) / "regions" / f"{scx}_{scz}"
        region_raw_path.mkdir(parents=True, exist_ok=True)

        if 'temperature' in stitched_layers:
            write_raw_json_grid(str(region_raw_path / "temperature.json"), stitched_layers['temperature'].tolist())
        if 'humidity' in stitched_layers:
            write_raw_json_grid(str(region_raw_path / "humidity.json"), stitched_layers['humidity'].tolist())

        # ЭТАП 4: НАРЕЗАЕМ ИЗМЕНЕННУЮ КАРТУ ОБРАТНО НА ЧАНКИ
        _apply_changes_to_chunks(stitched_layers, base_chunks, base_cx, base_cz, chunk_size)

        # ЭТАП 5: ОСТАЛЬНАЯ ПОЧАНКОВАЯ ОБРАБОТКА (БИОМЫ И ДР.)
        for chunk in base_chunks.values():
            apply_biomes_to_surface(chunk)

        print(f"[RegionProcessor] FINISHED for region ({scx}, {scz}).")
        return base_chunks