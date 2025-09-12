# Файл: game_engine_restructured/world/processing/region_processor.py
from __future__ import annotations
from typing import Dict, Tuple
import numpy as np
from pathlib import Path
import time

from ...core import constants as const
from ...core.preset import Preset
from ...core.types import GenResult
from ..grid_utils import _stitch_layers, _apply_changes_to_chunks, region_base
from ...algorithms.climate.climate import generate_climate_maps, apply_climate_to_surface
from ...algorithms.terrain.terrain import apply_slope_obstacles
from ..planners.water_planner import apply_sea_level, generate_highland_lakes
from ...core.export import write_raw_json_grid


class RegionProcessor:
    def __init__(self, preset: Preset, world_seed: int, artifacts_root: Path):
        self.preset = preset
        self.world_seed = world_seed
        self.artifacts_root = artifacts_root

    def process(self, scx: int, scz: int, base_chunks: Dict[Tuple[int, int], GenResult]) -> Dict[
        Tuple[int, int], GenResult]:

        t_start = time.perf_counter()
        timings = {}

        print(f"[RegionProcessor] STARTING for region ({scx}, {scz})...")

        first_chunk = next(iter(base_chunks.values()))
        chunk_size = first_chunk.size
        region_size = int(self.preset.region_size)

        region_pixel_size = region_size * chunk_size
        base_cx, base_cz = region_base(scx, scz, region_size)

        t_prev = time.perf_counter()

        # --- ИЗМЕНЕНИЕ: Теперь мы "склеиваем" все слои, включая высоты ---
        stitched_layers, _ = _stitch_layers(region_size, chunk_size, base_chunks,
                                            ['height', 'surface', 'navigation'])
        t_curr = time.perf_counter()
        timings['1_stitch_all_layers_ms'] = (t_curr - t_prev) * 1000
        t_prev = t_curr

        # --- ИЗМЕНЕНИЕ: Удалена ресурсоемкая генерация высот отсюда ---

        # ЭТАП 2: РЕГИОНАЛЬНАЯ ОБРАБОТКА
        apply_slope_obstacles(stitched_layers['height'], stitched_layers['surface'], self.preset)
        t_curr = time.perf_counter()
        timings['3_slopes_ms'] = (t_curr - t_prev) * 1000
        t_prev = t_curr

        apply_sea_level(stitched_layers['height'], stitched_layers['surface'], stitched_layers['navigation'],
                        self.preset)
        t_curr = time.perf_counter()
        timings['4_sea_level_ms'] = (t_curr - t_prev) * 1000
        t_prev = t_curr

        generate_climate_maps(stitched_layers, self.preset, self.world_seed, base_cx, base_cz, region_pixel_size,
                              region_size)
        t_curr = time.perf_counter()
        timings['5_climate_maps_ms'] = (t_curr - t_prev) * 1000
        t_prev = t_curr

        generate_highland_lakes(stitched_layers['height'], stitched_layers['surface'], stitched_layers['navigation'],
                                stitched_layers.get("humidity"), self.preset, self.world_seed)
        t_curr = time.perf_counter()
        timings['6_lakes_ms'] = (t_curr - t_prev) * 1000
        t_prev = t_curr

        # ЭТАП 3: НАРЕЗАЕМ КАРТУ ОБРАТНО НА ЧАНКИ

        for (cx, cz), chunk in base_chunks.items():
            x0 = (cx - base_cx) * chunk_size
            z0 = (cz - base_cz) * chunk_size
            # Используем exclusive срезы, как вы и предложили
            x1 = x0 + chunk_size
            z1 = z0 + chunk_size

            for name, grid in stitched_layers.items():
                # Вырезаем нужный фрагмент
                sub_grid_np = grid[z0:z1, x0:x1]

                # Проверка на корректность размера
                assert sub_grid_np.shape == (chunk_size, chunk_size), \
                    f"Chunk ({cx},{cz}) slice error! Expected ({chunk_size},{chunk_size}), got {sub_grid_np.shape}"

                # Конвертируем обратно в списки и сохраняем в чанк
                sub_grid_list = sub_grid_np.tolist()
                if name == 'height':
                    chunk.layers["height_q"]["grid"] = sub_grid_list
                # --- ИСПРАВЛЕНИЕ: Добавляем 'temperature' и 'humidity' в список слоев для нарезки ---
                elif name in ['surface', 'navigation', 'temperature', 'humidity']:
                    chunk.layers[name] = sub_grid_list

        # --- КОНЕЦ ИСПРАВЛЕНИЯ ---
        t_curr = time.perf_counter()
        timings['8_slice_to_chunks_ms'] = (t_curr - t_prev) * 1000
        t_prev = t_curr

        # ЭТАП 4: ПРИМЕНЯЕМ КЛИМАТ К ТЕКСТУРАМ
        for chunk in base_chunks.values():
            apply_climate_to_surface(chunk)
        t_curr = time.perf_counter()
        timings['9_apply_climate_ms'] = (t_curr - t_prev) * 1000
        t_prev = t_curr

        region_raw_path = self.artifacts_root / "world_raw" / str(self.world_seed) / "regions" / f"{scx}_{scz}"
        region_raw_path.mkdir(parents=True, exist_ok=True)
        if 'temperature' in stitched_layers:
            write_raw_json_grid(str(region_raw_path / "temperature.json"), stitched_layers['temperature'])
        if 'humidity' in stitched_layers:
            write_raw_json_grid(str(region_raw_path / "humidity.json"), stitched_layers['humidity'])
        t_curr = time.perf_counter()
        timings['10_save_debug_json_ms'] = (t_curr - t_prev) * 1000

        total_time_ms = (time.perf_counter() - t_start) * 1000
        timings['total_region_ms'] = total_time_ms

        print(f"[RegionProcessor] Timings for region ({scx}, {scz}):")
        for key, value in sorted(timings.items()):
            print(f"  - {key}: {value:.2f} ms")

        for chunk in base_chunks.values():
            if 'gen_timings_ms' not in chunk.metrics:
                chunk.metrics['gen_timings_ms'] = {}
            chunk.metrics['gen_timings_ms']['regional_processing'] = timings

        print(f"[RegionProcessor] FINISHED for region ({scx}, {scz}). Total time: {total_time_ms:.2f} ms")
        return base_chunks