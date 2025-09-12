# Файл: game_engine_restructured/world/regions.py
from __future__ import annotations
import concurrent.futures
from pathlib import Path
from typing import Dict, Tuple

from ..core.preset import Preset
from ..core.types import GenResult
from ..core.export import write_region_meta, write_raw_chunk
from .processing.base_processor import BaseProcessor
from .processing.region_processor import RegionProcessor
from .serialization import RegionMetaContract
from .planners.road_planner import plan_roads_for_region
from .planners.river_planner import plan_rivers_for_region
from .grid_utils import region_base, _stitch_layers


class RegionManager:
    def __init__(self, world_seed: int, preset: Preset, artifacts_root: Path):
        self.world_seed = world_seed
        self.preset = preset
        self.artifacts_root = artifacts_root
        self.raw_data_path = self.artifacts_root / "world_raw" / str(self.world_seed)
        self.base_processor = BaseProcessor(preset)
        self.region_processor = RegionProcessor(preset, world_seed, self.artifacts_root)
        self.base_chunk_cache: Dict[Tuple[int, int], GenResult] = {}

    def _generate_or_get_chunk_task(self, cx: int, cz: int) -> GenResult:
        """Задача для одного потока: получить или сгенерировать БАЗОВЫЙ чанк."""
        if (cx, cz) in self.base_chunk_cache:
            return self.base_chunk_cache[(cx, cz)]

        params = {"seed": self.world_seed, "cx": cx, "cz": cz}
        chunk_result = self.base_processor.process(params)
        self.base_chunk_cache[(cx, cz)] = chunk_result
        return chunk_result

    def generate_raw_region(self, scx: int, scz: int):
        region_meta_path = self.raw_data_path / "regions" / f"{scx}_{scz}" / "region_meta.json"
        if region_meta_path.exists():
            print(f"[RegionManager] Raw data for region ({scx},{scz}) already exists.")
            return

        print(f"[RegionManager] STARTING PIPELINE for region ({scx}, {scz})...")

        region_size = self.preset.region_size
        base_cx, base_cz = region_base(scx, scz, region_size)

        # --- ИЗМЕНЕНИЕ: Запрашиваем чанки с "фартуком" в 1 чанк ---
        tasks = []
        for dz in range(-1, region_size + 1):
            for dx in range(-1, region_size + 1):
                tasks.append((base_cx + dx, base_cz + dz))

        chunks_with_border: Dict[Tuple[int, int], GenResult] = {}
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future_to_chunk = {executor.submit(self._generate_or_get_chunk_task, cx, cz): (cx, cz) for cx, cz in tasks}
            for future in concurrent.futures.as_completed(future_to_chunk):
                try:
                    chunk_result = future.result()
                    key = (chunk_result.cx, chunk_result.cz)
                    chunks_with_border[key] = chunk_result
                except Exception as exc:
                    print(f"!!! Base chunk generation failed: {exc}")

        print(f"  -> Generated/loaded {len(chunks_with_border)} base chunks (with 1-chunk border).")

        processed_chunks = self.region_processor.process(scx, scz, chunks_with_border)

        # Для планировщиков и сохранения используем только чанки основного региона (без "фартука")
        final_chunks_for_region = {
            k: v for k, v in processed_chunks.items()
            if base_cx <= k[0] < base_cx + region_size and base_cz <= k[1] < base_cz + region_size
        }

        stitched_layers_for_planners, _ = _stitch_layers(
            region_size, self.preset.size, final_chunks_for_region, ['height', 'navigation']
        )
        road_plan = plan_roads_for_region(scx, scz, self.world_seed, self.preset, final_chunks_for_region)
        river_plan = plan_rivers_for_region(
            stitched_layers_for_planners['height'], stitched_layers_for_planners['navigation'], self.preset,
            self.world_seed
        )
        meta_contract = RegionMetaContract(
            scx=scx, scz=scz, world_seed=self.world_seed, road_plan=road_plan, river_plan=river_plan
        )
        write_region_meta(str(region_meta_path), meta_contract)

        for (cx, cz), chunk_data in final_chunks_for_region.items():
            path_prefix = str(self.raw_data_path / "chunks" / f"{cx}_{cz}")
            write_raw_chunk(path_prefix, chunk_data)

        print(f"[RegionManager] FINISHED RAW generation for region ({scx}, {scz}).")