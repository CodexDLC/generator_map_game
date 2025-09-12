# Файл: game_engine_restructured/world/processing/region_processor.py
from __future__ import annotations
import time
from pathlib import Path
from typing import Dict, Tuple
import numpy as np
from ...core import constants as const
from ...core.constants import SURFACE_ID_TO_KIND, NAV_ID_TO_KIND

from ..analytics.region_analysis import RegionAnalysis, _extract_core
from ...algorithms.climate.climate import generate_climate_maps
from ...core.preset import Preset
from ...core.types import GenResult
from ..grid_utils import _stitch_layers, region_base, _apply_changes_to_chunks

# --- ИЗМЕНЕНИЕ: Импортируем новые функции ---
from ...algorithms.terrain.terrain import generate_elevation_region, classify_terrain, apply_slope_obstacles

from ..planners.water_planner import (
    apply_sea_level,
    generate_highland_lakes,
    generate_rivers,
)

from ...core.export import write_raw_regional_layers

import os, time




class _Prof:
    def __init__(self, tag: str, enabled: bool = True):
        self.enabled = enabled
        self.tag = tag
        self.t0 = time.perf_counter()
        self.t = self.t0
        self.events = []

    def lap(self, name: str):
        if not self.enabled:
            return
        now = time.perf_counter()
        self.events.append((name, (now - self.t) * 1000.0))
        self.t = now

    def end(self):
        if not self.enabled:
            return
        total = (time.perf_counter() - self.t0) * 1000.0
        print(f"[PROFILE][{self.tag}] total_ms: {total:.2f}")
        for name, ms in self.events:
            print(f"[PROFILE][{self.tag}] {name}_ms: {ms:.2f}")
        print(f"[PROFILE][{self.tag}] ---")

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
        prof = _Prof(tag=f"{scx},{scz}", enabled=True)

        # --- sizes / scratch как у тебя ---
        preset_region_size = self.preset.region_size
        chunk_size = self.preset.size
        processing_region_size = preset_region_size + 2
        ext_size = processing_region_size * chunk_size
        scratch_a = np.empty((ext_size, ext_size), dtype=np.float32)
        scratch_b = np.empty((ext_size, ext_size), dtype=np.float32)
        scratch_buffers = {'a': scratch_a, 'b': scratch_b}

        stitched_layers_ext = {}
        stitched_layers_ext['height'] = generate_elevation_region(
            self.world_seed, scx, scz, preset_region_size, chunk_size, self.preset, scratch_buffers
        )

        stitched_surface_ext = np.empty((ext_size, ext_size), dtype=const.SURFACE_DTYPE)
        stitched_nav_ext = np.empty((ext_size, ext_size), dtype=const.NAV_DTYPE)
        classify_terrain(stitched_layers_ext['height'], stitched_surface_ext, stitched_nav_ext, self.preset)
        stitched_layers_ext['surface'] = stitched_surface_ext
        stitched_layers_ext['navigation'] = stitched_nav_ext

        assert stitched_surface_ext.dtype != object and stitched_nav_ext.dtype != object, \
            "surface/navigation must be numeric (IDs), not object"

        # море
        apply_sea_level(stitched_layers_ext['height'], stitched_layers_ext['surface'],
                        stitched_layers_ext['navigation'], self.preset)
        apply_slope_obstacles(stitched_layers_ext['height'], stitched_layers_ext['surface'], self.preset)

        prof.lap("t0_elevation_surface_sea")

        # t1: реки
        river_mask_ext = generate_rivers(
            stitched_layers_ext['height'],
            stitched_layers_ext['surface'],
            stitched_layers_ext['navigation'],
            self.preset,
            chunk_size
        )
        stitched_layers_ext['river'] = river_mask_ext
        prof.lap("t1_rivers")

        # t2: климат
        climate_maps = generate_climate_maps(
            stitched_layers_ext, self.preset, self.world_seed,
            0, 0, ext_size, scratch_buffers=scratch_buffers
        )
        stitched_layers_ext.update(climate_maps)
        prof.lap("t2_climate")

        # t3: озёра
        generate_highland_lakes(
            stitched_layers_ext['height'],
            stitched_layers_ext['surface'],
            stitched_layers_ext['navigation'],
            stitched_layers_ext.get("humidity"),
            self.preset, self.world_seed
        )
        prof.lap("t3_lakes")

        # t4: аналитика
        analysis = RegionAnalysis(scx, scz, stitched_layers_ext, chunk_size)
        neighbor_data = {
            "north": self.processed_region_cache.get((scx, scz - 1)),
            "west": self.processed_region_cache.get((scx - 1, scz)),
        }
        analysis.run(neighbor_data)
        analysis.print_report()
        self.processed_region_cache[(scx, scz)] = analysis.layers_core.copy()
        final_layers_core = analysis.layers_core
        prof.lap("t4_analysis")

        # t5: нарезка + биомы + экспорт
        base_cx, base_cz = region_base(scx, scz, preset_region_size)
        final_chunks = {
            k: v for k, v in chunks_with_border.items()
            if base_cx <= k[0] < base_cx + preset_region_size and base_cz <= k[1] < base_cz + preset_region_size
        }
        _apply_changes_to_chunks(final_layers_core, final_chunks, base_cx, base_cz, chunk_size)

        for chunk in final_chunks.values():
            # конверсия surface/nav в текстовые только здесь — после нарезки
            if isinstance(chunk.layers.get('surface'), np.ndarray):
                sid = chunk.layers['surface']
                chunk.layers['surface'] = [[SURFACE_ID_TO_KIND.get(int(x), "base_dirt") for x in row] for row in sid]
            if isinstance(chunk.layers.get('navigation'), np.ndarray):
                nid = chunk.layers['navigation']
                chunk.layers['navigation'] = [[NAV_ID_TO_KIND.get(int(x), "obstacle_prop") for x in row] for row in nid]
            apply_biomes_to_surface(chunk, self.preset)

        region_raw_path = self.artifacts_root / "world_raw" / str(self.world_seed) / "regions" / f"{scx}_{scz}"
        layers_to_save = {k: v for k, v in final_layers_core.items() if
                          k in ['temperature', 'humidity', 'shadow', 'coast', 'river', 'temp_dry']}
        if layers_to_save:
            write_raw_regional_layers(str(region_raw_path / "climate_layers.npz"), layers_to_save, verbose=True)
        prof.lap("t5_slice_biomes_export")

        prof.end()  # печать сводки профиля




        print(
            f"[RegionProcessor] FINISHED for region ({scx}, {scz}). Total time: {(time.perf_counter() - t_start) * 1000:.2f} ms")
        return final_chunks
