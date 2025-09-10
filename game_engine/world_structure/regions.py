# REWRITTEN FILE: game_engine/world_structure/regions.py
from __future__ import annotations

import dataclasses
import json
from pathlib import Path
from typing import Dict, Tuple

from ..core.preset import Preset
from ..core.types import GenResult
from ..core.export import write_region_meta
from ..generators._base.generator import BaseGenerator
from .serialization import RegionMetaContract
from .planners.road_planner import plan_roads_for_region
from .planners.biome_planner import assign_biome_to_region


# --- CHANGE: Import grid utils from the new file ---
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
        Генерирует и сохраняет "сырую" версию региона (ЭТАП 1).
        """
        region_meta_path = (
            self.raw_data_path / "regions" / f"{scx}_{scz}" / "region_meta.json"
        )
        if region_meta_path.exists():
            print(f"[RegionManager] Raw data for region ({scx},{scz}) already exists.")
            return

        print(f"[RegionManager] STARTING RAW generation for region ({scx}, {scz})...")

        # --- ИЗМЕНЕНИЕ: Берем размер региона из пресета ---
        region_size = self.preset.region_size
        base_cx, base_cz = region_base(scx, scz, region_size)

        base_chunks: Dict[Tuple[int, int], GenResult] = {}
        for dz in range(region_size):
            for dx in range(region_size):
                cx, cz = base_cx + dx, base_cz + dz
                params = {"seed": self.world_seed, "cx": cx, "cz": cz}
                base_chunks[(cx, cz)] = self.base_generator.generate(params)

        biome_type = assign_biome_to_region(self.world_seed, scx, scz)
        road_plan = plan_roads_for_region(
            scx, scz, self.world_seed, self.preset, base_chunks, biome_type
        )

        # 3. Save raw data to disk

        # --- ИСПРАВЛЕНИЕ: Мы создаем контракт с ОРИГИНАЛЬНЫМ road_plan (с кортежами) ---
        # Преобразованием в строки теперь будет заниматься функция write_region_meta
        meta_contract = RegionMetaContract(
            scx=scx, scz=scz, world_seed=self.world_seed, road_plan=road_plan
        )
        write_region_meta(str(region_meta_path), meta_contract)

        # Сохраняем "облегченные" сырые чанки (эта часть остается без изменений)
        for (cx, cz), chunk_data in base_chunks.items():
            raw_chunk_path = self.raw_data_path / "chunks" / f"{cx}_{cz}.json"
            raw_chunk_path.parent.mkdir(parents=True, exist_ok=True)
            lean_raw_data = {
                "version": chunk_data.version,
                "type": chunk_data.type,
                "seed": chunk_data.seed,
                "cx": chunk_data.cx,
                "cz": chunk_data.cz,
                "size": chunk_data.size,
                "cell_size": chunk_data.cell_size,
                # --- ИЗМЕНЕНИЯ ЗДЕСЬ ---
                "grid_spec": dataclasses.asdict(chunk_data.grid_spec) if chunk_data.grid_spec else None,
                # ---------------------
                "layers": chunk_data.layers,
                "ports": chunk_data.ports,
                "capabilities": chunk_data.capabilities,
                "stage_seeds": chunk_data.stage_seeds,
            }
            with open(raw_chunk_path, "w", encoding="utf-8") as f:
                json.dump(lean_raw_data, f, indent=2)

        print(f"[RegionManager] FINISHED RAW generation for region ({scx}, {scz}).")
