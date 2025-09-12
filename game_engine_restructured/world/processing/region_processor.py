# Файл: game_engine_restructured/world/processing/region_processor.py
from __future__ import annotations
import time
from pathlib import Path
from typing import Dict, Tuple
import numpy as np
# --- ИСПРАВЛЕНИЕ: Заменяем импорт ---
from ...core import constants as const

from ..analytics.region_analysis import RegionAnalysis, _extract_core
from ...algorithms.climate.climate import generate_climate_maps
from ...core.preset import Preset
from ...core.types import GenResult
from ..grid_utils import _stitch_layers, region_base

from ...algorithms.terrain.terrain import apply_slope_obstacles

from ..planners.water_planner import (
    apply_sea_level,
    generate_highland_lakes,
    generate_rivers,
)

from ...core.export import write_raw_regional_layers


def apply_biomes_to_surface(chunk, preset):
    pass


class RegionProcessor:
    def __init__(self, preset: Preset, world_seed: int, artifacts_root: Path):
        self.preset = preset
        self.world_seed = world_seed
        self.artifacts_root = artifacts_root
        self.processed_region_cache: Dict[Tuple[int, int], Dict[str, np.ndarray]] = {}

    def process(self, scx: int, scz: int, chunks_with_border: Dict[Tuple[int, int], GenResult]) -> Dict[
        Tuple[int, int], GenResult]:

        t_start = time.perf_counter()
        print(f"[RegionProcessor] STARTING for region ({scx}, {scz})...")

        preset_region_size = self.preset.region_size
        chunk_size = self.preset.size
        processing_region_size = preset_region_size + 2

        # --- УПРАВЛЕНИЕ ПАМЯТЬЮ: Создаем scratch-буферы ---
        ext_size = processing_region_size * chunk_size
        scratch_a = np.empty((ext_size, ext_size), dtype=np.float32)
        scratch_b = np.empty((ext_size, ext_size), dtype=np.float32)

        stitched_layers_ext, (base_cx_bordered, base_cz_bordered) = _stitch_layers(
            processing_region_size, chunk_size, chunks_with_border,
            ['height', 'surface', 'navigation']
        )

        # Этап 1: Базовый рельеф и вода
        apply_slope_obstacles(stitched_layers_ext['height'], stitched_layers_ext['surface'], self.preset)
        apply_sea_level(stitched_layers_ext['height'], stitched_layers_ext['surface'],
                        stitched_layers_ext['navigation'], self.preset)

        # Этап 2: Генерация рек (единый источник истины)
        river_mask_ext = generate_rivers(stitched_layers_ext['height'], self.preset, chunk_size)
        stitched_layers_ext['river'] = river_mask_ext

        # Применяем физические изменения от рек
        stitched_layers_ext['height'][river_mask_ext] -= 1.0
        stitched_layers_ext['surface'][river_mask_ext] = const.KIND_BASE_WATERBED
        stitched_layers_ext['navigation'][river_mask_ext] = const.NAV_WATER

        # Этап 3: Климат, который теперь зависит от надежной карты рек
        climate_maps = generate_climate_maps(
            stitched_layers_ext, self.preset, self.world_seed,
            base_cx_bordered, base_cz_bordered,
            ext_size,
            scratch_buffers={'a': scratch_a, 'b': scratch_b} # Передаем буферы
        )
        stitched_layers_ext.update(climate_maps)

        # Этап 4: Озера (могут немного влиять на влажность)
        generate_highland_lakes(stitched_layers_ext['height'], stitched_layers_ext['surface'],
                                stitched_layers_ext['navigation'],
                                stitched_layers_ext.get("humidity"), self.preset, self.world_seed)

        # Этап 5: Аналитика и кэширование
        analysis = RegionAnalysis(scx, scz, stitched_layers_ext, chunk_size)
        neighbor_data = {
            "north": self.processed_region_cache.get((scx, scz - 1)),
            "west": self.processed_region_cache.get((scx - 1, scz)),
        }
        analysis.run(neighbor_data)
        analysis.print_report()

        self.processed_region_cache[(scx, scz)] = analysis.layers_core.copy()
        final_layers_core = analysis.layers_core

        # Этап 6: Нарезка и применение биомов
        base_cx, base_cz = region_base(scx, scz, preset_region_size)
        final_chunks = {}
        for dz in range(preset_region_size):
            for dx in range(preset_region_size):
                cx, cz = base_cx + dx, base_cz + dz
                chunk = chunks_with_border.get((cx, cz))
                if not chunk: continue
                final_chunks[(cx, cz)] = chunk

                x0, z0 = dx * chunk_size, dz * chunk_size
                for name, grid in final_layers_core.items():
                    # Проверяем, что слой существует в чанке или это высота
                    if name in chunk.layers or name == 'height' or name in climate_maps:
                        sub_grid_np = grid[z0:z0 + chunk_size, x0:x0 + chunk_size]
                        if name == 'height':
                            chunk.layers["height_q"]["grid"] = sub_grid_np.tolist()
                        else:
                            # Копируем все слои (включая климатические) в чанк
                            chunk.layers[name] = sub_grid_np.tolist()

        for chunk in final_chunks.values():
            apply_biomes_to_surface(chunk, self.preset)

        # Этап 7: Сохранение артефактов
        region_raw_path = self.artifacts_root / "world_raw" / str(self.world_seed) / "regions" / f"{scx}_{scz}"
        layers_to_save = {k: v for k, v in final_layers_core.items() if
                          k in ['temperature', 'humidity', 'shadow', 'coast', 'river', 'temp_dry']}
        if layers_to_save:
            write_raw_regional_layers(str(region_raw_path / "climate_layers.npz"), layers_to_save)

        print(
            f"[RegionProcessor] FINISHED for region ({scx}, {scz}). Total time: {(time.perf_counter() - t_start) * 1000:.2f} ms")
        return final_chunks