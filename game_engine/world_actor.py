# game_engine/world_actor.py
from __future__ import annotations
from pathlib import Path
import json

from .core.preset import Preset
from .core.export import (
    write_client_chunk, write_chunk_preview, write_heightmap_r16, write_control_map_r32
)
# --- ИЗМЕНЕНИЕ: Импортируем region_key из нового места ---
from .world_structure.grid_utils import region_key, region_base
from .world_structure.regions import RegionManager
from .world_structure.chunk_processor import process_chunk
from .world_structure.context import Region
from .world_structure.road_types import RoadWaypoint, ChunkRoadPlan
from .world_structure.serialization import ClientChunkContract


class WorldActor:
    def __init__(self, seed: int, preset: Preset, artifacts_root: Path, progress_callback=None):
        self.seed = seed
        self.preset = preset
        self.artifacts_root = artifacts_root
        self.raw_data_path = self.artifacts_root / "world_raw" / str(self.seed)
        self.final_data_path = self.artifacts_root / "world" / "world_location" / str(self.seed)
        self.progress_callback = progress_callback

    def _log(self, message: str):
        if self.progress_callback:
            self.progress_callback(message)

    def prepare_starting_area(self, region_manager: RegionManager):
        radius = self.preset.initial_load_radius
        print(
            f"\n[WorldActor] Preparing start area with radius {radius} ({(radius * 2) + 1}x{(radius * 2) + 1} chunks)...")
        regions_to_ensure = set()
        for cz in range(-radius, radius + 1):
            for cx in range(-radius, radius + 1):
                # --- ИЗМЕНЕНИЕ: Передаем region_size из пресета ---
                regions_to_ensure.add(region_key(cx, cz, self.preset.region_size))

        for scx, scz in regions_to_ensure:
            # --- ИЗМЕНЕНИЕ: Передаем region_size из пресета ---
            base_cx, _ = region_base(scx, scz, self.preset.region_size)
            self.ensure_region_is_ready(base_cx, 0, region_manager)  # cz можно оставить 0

    def ensure_region_is_ready(self, cx: int, cz: int, region_manager: RegionManager):
        scx, scz = region_key(cx, cz, self.preset.region_size)
        region_manager.generate_raw_region(scx, scz)

        final_chunk_path_check = self.final_data_path / f"{cx}_{cz}" / "chunk.rle.json"
        if final_chunk_path_check.exists():
            self._log(f"Final chunks for region ({scx},{scz}) already exist. Skipping detailing.")
            return

        self._log(f"[WorldActor] Detailing required for region ({scx},{scz})...")
        region_meta_path = self.raw_data_path / "regions" / f"{scx}_{scz}" / "region_meta.json"
        with open(region_meta_path, 'r', encoding='utf-8') as f:
            meta_data = json.load(f)
            deserialized_road_plan = {}
            road_plan_from_json = meta_data.get("road_plan", {})
            for key_str, plan_dict in road_plan_from_json.items():
                cx_str, cz_str = key_str.split(',');
                chunk_key = (int(cx_str), int(cz_str))
                new_plan = ChunkRoadPlan();
                new_plan.waypoints = [RoadWaypoint(**wp_dict) for wp_dict in plan_dict.get("waypoints", [])]
                deserialized_road_plan[chunk_key] = new_plan
            region_context = Region(scx=scx, scz=scz, biome_type="placeholder_biome", road_plan=deserialized_road_plan)

        region_size = self.preset.region_size
        base_cx, base_cz = region_base(scx, scz, region_size)
        total_chunks = region_size * region_size
        chunk_list = [(dz, dx) for dz in range(region_size) for dx in range(region_size)]

        for i, (dz, dx) in enumerate(chunk_list):
            chunk_cx, chunk_cz = base_cx + dx, base_cz + dz
            self._log(f"  -> Detailing chunk ({chunk_cx},{chunk_cz}) [{i + 1}/{total_chunks}]...")
            raw_chunk_path = self.raw_data_path / "chunks" / f"{chunk_cx}_{chunk_cz}.json"
            final_chunk = process_chunk(self.preset, raw_chunk_path, region_context)

            # --- ИЗМЕНЕНИЕ: Извлекаем все три слоя ---
            surface_grid = final_chunk.layers.get("surface", [])
            nav_grid = final_chunk.layers.get("navigation", [])
            overlay_grid = final_chunk.layers.get("overlay", [])  # <-- Добавлена эта строка
            height_grid = final_chunk.layers.get("height_q", {}).get("grid", [])

            if not surface_grid or not nav_grid or not height_grid:
                self._log(
                    f"!!! [WorldActor] ERROR: Chunk ({chunk_cx},{chunk_cz}) missing essential layers. Skipping export.")
                continue

            client_chunk_dir = self.final_data_path / f"{chunk_cx}_{chunk_cz}"
            client_rle_path = client_chunk_dir / "chunk.rle.json"
            heightmap_path = client_chunk_dir / "heightmap.r16"
            controlmap_path = client_chunk_dir / "control.r32"
            preview_path = client_chunk_dir / "preview.png"
            palette = self.preset.export.get("palette", {})
            max_height = float(self.preset.elevation.get("max_height_m", 1.0))
            client_contract = ClientChunkContract(cx=chunk_cx, cz=chunk_cz, layers=final_chunk.layers)

            write_client_chunk(str(client_rle_path), client_contract)
            write_heightmap_r16(str(heightmap_path), height_grid, max_height)

            # --- ИЗМЕНЕНИЕ: Передаем overlay_grid в функцию ---
            write_control_map_r32(str(controlmap_path), surface_grid, nav_grid, overlay_grid)

            write_chunk_preview(str(preview_path), surface_grid, nav_grid, palette)

        self._log(f"[WorldActor] Detailing for region ({scx},{scz}) is complete.")
