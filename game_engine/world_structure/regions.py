# REWRITTEN FILE: game_engine/world_structure/regions.py
from __future__ import annotations
import json
import dataclasses
from pathlib import Path
from typing import Dict, Tuple

from ..core.preset import Preset
from ..core.types import GenResult
from ..core.export import write_region_meta
from ..generators._base.generator import BaseGenerator
from .serialization import RegionMetaContract
from .planners.road_planner import plan_roads_for_region
from .planners.biome_planner import assign_biome_to_region
from .context import Region

# --- CHANGE: Import grid utils from the new file ---
from .grid_utils import region_base, REGION_SIZE


class RegionManager:
    def __init__(self, world_seed: int, preset: Preset, base_generator: BaseGenerator, artifacts_root: Path):
        self.world_seed = world_seed
        self.preset = preset
        self.base_generator = base_generator
        self.artifacts_root = artifacts_root
        self.raw_data_path = self.artifacts_root / "world_raw" / str(self.world_seed)

    def generate_raw_region(self, scx: int, scz: int):
        """
        Generates and saves the 'raw' version of a region, including the base landscape
        and global plans. This is STAGE 1 of the generation pipeline.
        """
        region_meta_path = self.raw_data_path / "regions" / f"{scx}_{scz}" / "region_meta.json"
        if region_meta_path.exists():
            print(f"[RegionManager] Raw data for region ({scx},{scz}) already exists.")
            return

        print(f"[RegionManager] STARTING RAW generation for region ({scx}, {scz})...")
        base_cx, base_cz = region_base(scx, scz)

        # 1. Create base landscape in memory
        base_chunks: Dict[Tuple[int, int], GenResult] = {}
        for dz in range(REGION_SIZE):
            for dx in range(REGION_SIZE):
                cx, cz = base_cx + dx, base_cz + dz
                params = {"seed": self.world_seed, "cx": cx, "cz": cz}
                base_chunks[(cx, cz)] = self.base_generator.generate(params)

        # 2. Perform global planning
        biome_type = assign_biome_to_region(self.world_seed, scx, scz)
        road_plan = plan_roads_for_region(scx, scz, self.world_seed, self.preset, base_chunks)

        # 3. Save raw data to disk
        meta_contract = RegionMetaContract(scx=scx, scz=scz, world_seed=self.world_seed, road_plan=road_plan)
        write_region_meta(str(region_meta_path), meta_contract)

        for (cx, cz), chunk_data in base_chunks.items():
            raw_chunk_path = self.raw_data_path / "chunks" / f"{cx}_{cz}.json"
            raw_chunk_path.parent.mkdir(parents=True, exist_ok=True)

            # --- ИЗМЕНЕНИЕ: Собираем только нужные данные для сырого чанка ---
            lean_raw_data = {
                "version": chunk_data.version,
                "type": chunk_data.type,
                "seed": chunk_data.seed,
                "cx": chunk_data.cx,
                "cz": chunk_data.cz,
                "size": chunk_data.size,
                "cell_size": chunk_data.cell_size,
                "layers": chunk_data.layers,
                "ports": chunk_data.ports,
                "capabilities": chunk_data.capabilities,
                # Добавляем stage_seeds, так как они могут понадобиться для консистентной детализации
                "stage_seeds": chunk_data.stage_seeds
            }
            # --- КОНЕЦ ИЗМЕНЕНИЯ ---

            with open(raw_chunk_path, 'w', encoding='utf-8') as f:
                # Сериализуем не весь объект, а только наш "облегченный" словарь
                json.dump(lean_raw_data, f, indent=2)

        print(f"[RegionManager] FINISHED RAW generation for region ({scx}, {scz}).")