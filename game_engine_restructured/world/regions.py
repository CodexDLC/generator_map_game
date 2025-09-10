# Файл: game_engine/world/regions.py (ОТЛАДОЧНАЯ ВЕРСИЯ)
from __future__ import annotations
import dataclasses
import json
from pathlib import Path
from typing import Dict, Tuple

from ..core.preset import Preset
from ..core.types import GenResult
from ..core.export import write_region_meta
from ..generators.base.generator import BaseGenerator
from .serialization import RegionMetaContract
from .planners.road_planner import plan_roads_for_region
from .planners.biome_planner import assign_biome_to_region
from .grid_utils import region_base

class RegionManager:
    def __init__(
        self,
        world_seed: int,
        preset: Preset,
        base_generator: BaseGenerator,
        artifacts_root: Path,
    ):
        self.world_seed = world_seed
        self.preset = preset
        self.base_generator = base_generator
        self.artifacts_root = artifacts_root
        self.raw_data_path = self.artifacts_root / "world_raw" / str(self.world_seed)

    def generate_raw_region(self, scx: int, scz: int):
        """
        Генерирует "сырую" версию региона ПОСЛЕДОВАТЕЛЬНО для отладки.
        """
        region_meta_path = (
            self.raw_data_path / "regions" / f"{scx}_{scz}" / "region_meta.json"
        )
        if region_meta_path.exists():
            print(f"[RegionManager] Raw data for region ({scx},{scz}) already exists.")
            return

        print(f"[RegionManager] STARTING SEQUENTIAL generation for region ({scx}, {scz})...")

        region_size = self.preset.region_size
        base_cx, base_cz = region_base(scx, scz, region_size)

        # --- ИЗМЕНЕНИЕ: ВРЕМЕННО ВЫПОЛНЯЕМ ПОСЛЕДОВАТЕЛЬНО ---
        base_chunks: Dict[Tuple[int, int], GenResult] = {}
        total_chunks = region_size * region_size
        current_chunk = 0
        for dz in range(region_size):
            for dx in range(region_size):
                current_chunk += 1
                cx, cz = base_cx + dx, base_cz + dz
                print(f"  -> Generating chunk ({cx}, {cz}) [{current_chunk}/{total_chunks}]...")
                params = {"seed": self.world_seed, "cx": cx, "cz": cz}
                chunk_result = self.base_generator.generate(params)
                base_chunks[(cx, cz)] = chunk_result
        # --- КОНЕЦ ИЗМЕНЕНИЯ ---

        print("[RegionManager] -> All chunks generated successfully.")

        biome_type = assign_biome_to_region(self.world_seed, scx, scz)
        road_plan = plan_roads_for_region(
            scx, scz, self.world_seed, self.preset, base_chunks, biome_type
        )

        meta_contract = RegionMetaContract(
            scx=scx, scz=scz, world_seed=self.world_seed, road_plan=road_plan
        )
        write_region_meta(str(region_meta_path), meta_contract)

        for (cx, cz), chunk_data in base_chunks.items():
            raw_chunk_path = self.raw_data_path / "chunks" / f"{cx}_{cz}.json"
            raw_chunk_path.parent.mkdir(parents=True, exist_ok=True)
            lean_raw_data = {
                "version": chunk_data.version, "type": chunk_data.type,
                "seed": chunk_data.seed, "cx": chunk_data.cx, "cz": chunk_data.cz,
                "size": chunk_data.size, "cell_size": chunk_data.cell_size,
                "grid_spec": dataclasses.asdict(chunk_data.grid_spec) if chunk_data.grid_spec else None,
                "layers": chunk_data.layers, "ports": chunk_data.ports,
                "capabilities": chunk_data.capabilities, "stage_seeds": chunk_data.stage_seeds,
            }
            with open(raw_chunk_path, "w", encoding="utf-8") as f:
                json.dump(lean_raw_data, f, indent=2)

        print(f"[RegionManager] FINISHED RAW generation for region ({scx}, {scz}).")