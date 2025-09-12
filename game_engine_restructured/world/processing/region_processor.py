# Файл: game_engine_restructured/world/processing/region_processor.py
from __future__ import annotations
from typing import Dict, Tuple
import time

from ..analytics.region_analysis import RegionAnalysis
from ...core.preset import Preset
from ...core.types import GenResult
from ..grid_utils import _stitch_layers, region_base
from ...algorithms.climate.climate import generate_climate_maps, apply_climate_to_surface
from ...algorithms.terrain.terrain import apply_slope_obstacles
from ..planners.water_planner import apply_sea_level, generate_highland_lakes
from ...core.export import write_raw_regional_layers


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

        # --- ИЗМЕНЕНИЕ: Работаем с областью + "фартук" ---
        processing_region_size = preset_region_size + 2
        stitched_layers, (base_cx_bordered, base_cz_bordered) = _stitch_layers(
            processing_region_size, chunk_size, chunks_with_border,
            ['height', 'surface', 'navigation']
        )

        # --- Обработка на расширенной карте ---
        apply_slope_obstacles(stitched_layers['height'], stitched_layers['surface'], self.preset)
        apply_sea_level(stitched_layers['height'], stitched_layers['surface'], stitched_layers['navigation'],
                        self.preset)

        climate_maps = generate_climate_maps(
            stitched_layers, self.preset, self.world_seed,
            base_cx_bordered, base_cz_bordered,
            processing_region_size * chunk_size
        )
        stitched_layers.update(climate_maps)

        generate_highland_lakes(stitched_layers['height'], stitched_layers['surface'], stitched_layers['navigation'],
                                stitched_layers.get("humidity"), self.preset, self.world_seed)

        # --- Анализ и отчёт (на полной карте, до обрезки) ---
        analysis = RegionAnalysis(scx, scz, stitched_layers)
        neighbor_data = {
            "north": self.processed_region_cache.get((scx, scz - 1)),
            "south": self.processed_region_cache.get((scx, scz + 1)),
            "west": self.processed_region_cache.get((scx - 1, scz)),
            "east": self.processed_region_cache.get((scx + 1, scz)),
        }
        analysis.run(neighbor_data)
        analysis.print_report()

        # --- ИЗМЕНЕНИЕ: Обрезаем "фартук" ---
        border_px = chunk_size
        final_layers = {}
        for name, grid in stitched_layers.items():
            if grid.ndim == 2:
                final_layers[name] = grid[border_px:-border_px, border_px:-border_px]

        self.processed_region_cache[(scx, scz)] = final_layers.copy()

        # --- Нарезка и сохранение ---
        base_cx, base_cz = region_base(scx, scz, preset_region_size)
        final_chunks = {}
        for dz in range(preset_region_size):
            for dx in range(preset_region_size):
                cx, cz = base_cx + dx, base_cz + dz
                chunk = chunks_with_border.get((cx, cz))
                if not chunk: continue
                final_chunks[(cx, cz)] = chunk

                x0, z0 = dx * chunk_size, dz * chunk_size
                for name, grid in final_layers.items():
                    if name in chunk.layers or name == 'height':
                        sub_grid_np = grid[z0:z0 + chunk_size, x0:x0 + chunk_size]
                        if name == 'height':
                            chunk.layers["height_q"]["grid"] = sub_grid_np.tolist()
                        else:
                            chunk.layers[name] = sub_grid_np.tolist()

        for chunk in final_chunks.values():
            apply_climate_to_surface(chunk)

        region_raw_path = self.artifacts_root / "world_raw" / str(self.world_seed) / "regions" / f"{scx}_{scz}"
        layers_to_save = {k: v for k, v in final_layers.items() if
                          k in ['temperature', 'humidity', 'shadow', 'coast', 'river', 'temp_dry']}
        if layers_to_save:
            write_raw_regional_layers(str(region_raw_path / "climate_layers.npz"), layers_to_save)

        print(
            f"[RegionProcessor] FINISHED for region ({scx}, {scz}). Total time: {(time.perf_counter() - t_start) * 1000:.2f} ms")
        return final_chunks