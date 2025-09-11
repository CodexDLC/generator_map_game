# Файл: game_engine/world/regions.py
from __future__ import annotations
import dataclasses
import json
from pathlib import Path
from typing import Dict, Tuple
import concurrent.futures

from ..core.preset import Preset
from ..core.types import GenResult
from ..core.export import write_region_meta, write_raw_chunk
from .processing.base_processor import BaseProcessor
from .processing.region_processor import RegionProcessor

# --- НАЧАЛО ИЗМЕНЕНИЙ В ИМПОРТАХ ---
from .serialization import RegionMetaContract
from .planners.road_planner import plan_roads_for_region
from .planners.river_planner import plan_rivers_for_region, RiverPlan
from .grid_utils import region_base, _stitch_layers  # <--- ДОБАВЛЯЕМ НУЖНЫЕ ИМПОРТЫ


# --- КОНЕЦ ИЗМЕНЕНИЙ В ИМПОРТАХ ---


class RegionManager:
    def __init__(
            self,
            world_seed: int,
            preset: Preset,
            artifacts_root: Path,
    ):
        self.world_seed = world_seed
        self.preset = preset
        self.artifacts_root = artifacts_root
        self.raw_data_path = self.artifacts_root / "world_raw" / str(self.world_seed)

        self.base_processor = BaseProcessor(preset)
        self.region_processor = RegionProcessor(preset, world_seed, self.artifacts_root)

    def _generate_chunk_task(self, cx: int, cz: int) -> Tuple[Tuple[int, int], GenResult]:
        """Задача для одного потока: сгенерировать БАЗОВЫЙ чанк."""
        print(f"  -> Generating base chunk ({cx}, {cz})...")
        params = {"seed": self.world_seed, "cx": cx, "cz": cz}
        return (cx, cz), self.base_processor.process(params)

    def generate_raw_region(self, scx: int, scz: int):
        region_meta_path = (
                self.raw_data_path / "regions" / f"{scx}_{scz}" / "region_meta.json"
        )
        if region_meta_path.exists():
            print(f"[RegionManager] Raw data for region ({scx},{scz}) already exists.")
            return

        print(f"[RegionManager] STARTING PIPELINE for region ({scx}, {scz})...")

        region_size = self.preset.region_size
        base_cx, base_cz = region_base(scx, scz, region_size)

        tasks = [(base_cx + dx, base_cz + dz) for dz in range(region_size) for dx in range(region_size)]

        base_chunks: Dict[Tuple[int, int], GenResult] = {}
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future_to_chunk = {executor.submit(self._generate_chunk_task, cx, cz): (cx, cz) for cx, cz in tasks}
            for future in concurrent.futures.as_completed(future_to_chunk):
                try:
                    key, chunk_result = future.result()
                    base_chunks[key] = chunk_result
                except Exception as exc:
                    print(f"!!! Base chunk generation failed: {exc}")

        if len(base_chunks) != len(tasks):
            print(f"!!! [RegionManager] ERROR: Not all base chunks generated. Halting.")
            return
        print("[RegionManager] -> All base chunks generated.")

        processed_chunks = self.region_processor.process(scx, scz, base_chunks)

        # --- НАЧАЛО ИСПРАВЛЕННОГО БЛОКА ---
        # Получаем "сшитые" карты из обработанных чанков для планировщиков
        stitched_layers, _ = _stitch_layers(
            self.preset.region_size, self.preset.size, processed_chunks,
            ['height', 'navigation']
        )

        # 1. Планируем дороги
        road_plan = plan_roads_for_region(
            scx, scz, self.world_seed, self.preset, processed_chunks
        )

        # 2. Планируем реки
        river_plan = plan_rivers_for_region(
            stitched_layers['height'],
            stitched_layers['navigation'],
            self.preset,
            self.world_seed
        )

        # 3. Сохраняем ВСЕ планы в мета-файл
        meta_contract = RegionMetaContract(
            scx=scx, scz=scz, world_seed=self.world_seed,
            road_plan=road_plan,
            river_plan=river_plan
        )
        # --- КОНЕЦ ИСПРАВЛЕННОГО БЛОКА ---

        write_region_meta(str(region_meta_path), meta_contract)

        # Сохраняем финальные "сырые" чанки
        for (cx, cz), chunk_data in processed_chunks.items():
            path_prefix = str(self.raw_data_path / "chunks" / f"{cx}_{cz}")
            write_raw_chunk(path_prefix, chunk_data)

        print(f"[RegionManager] FINISHED RAW generation for region ({scx}, {scz}).")