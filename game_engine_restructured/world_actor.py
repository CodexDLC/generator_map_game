# Файл: game_engine/world_actor.py
from __future__ import annotations
import os
from pathlib import Path
import json

# --- НАЧАЛО ИЗМЕНЕНИЙ ---

from .core.preset import Preset
from .core.export import (
    write_client_chunk_meta,
    write_chunk_preview,
    write_heightmap_r16,
    write_control_map_r32,
    write_world_meta_json,
    write_objects_json,
    write_navigation_rle,
    write_server_hex_map
)
from .world.grid_utils import region_base
from .world.regions import RegionManager
from .world.chunk_processor import process_chunk
from .world.context import Region
from .world.road_types import RoadWaypoint, ChunkRoadPlan
from .world.prefab_manager import PrefabManager
from .world.serialization import ClientChunkContract

# --- КОНЕЦ ИЗМЕНЕНИЙ ---


class WorldActor:
    def __init__(
            self, seed: int, preset: Preset, artifacts_root: Path, progress_callback=None
    ):
        self.seed = seed
        self.preset = preset
        self.artifacts_root = artifacts_root
        self.raw_data_path = self.artifacts_root / "world_raw" / str(self.seed)
        self.final_data_path = (
                self.artifacts_root / "world" / "world_location" / str(self.seed)
        )
        self.progress_callback = progress_callback

        # --- ИЗМЕНЕНИЕ: Путь к файлу с данными ---
        prefabs_path = Path(__file__).parent / "data" / "prefabs.json"
        self.prefab_manager = PrefabManager(prefabs_path)

    def _log(self, message: str):
        if self.progress_callback:
            self.progress_callback(message)

    def prepare_starting_area(self, region_manager: RegionManager):
        radius = self.preset.initial_load_radius
        print(f"\n[WorldActor] Preparing start area with REGION radius {radius}...")

        regions_to_generate = []
        for scz in range(-radius, radius + 1):
            for scx in range(-radius, radius + 1):
                regions_to_generate.append((scx, scz))

        total_regions = len(regions_to_generate)
        print(f"[WorldActor] Found {total_regions} regions to generate.")

        for i, (scx, scz) in enumerate(regions_to_generate):
            print(f"\n--- [{i + 1}/{total_regions}] Processing Region ({scx}, {scz}) ---")
            region_manager.generate_raw_region(scx, scz)
            self._detail_region(scx, scz)

    def _detail_region(self, scx: int, scz: int):
        WORLD_ID = "world_location"
        meta_path = str(self.final_data_path.parent / "_world_meta.json")
        if not os.path.exists(meta_path):
            # VVV ИЗМЕНЕНИЕ ЗДЕСЬ VVV
            write_world_meta_json(
                meta_path, world_id=WORLD_ID, hex_edge_m=0.63, meters_per_pixel=0.5,
                chunk_px=self.preset.size, height_min_m=0.0,
                height_max_m=self.preset.elevation.get("max_height_m", 150.0),
            )
        self._log(f"[WorldActor] Detailing required for region ({scx},{scz})...")
        region_meta_path = self.raw_data_path / "regions" / f"{scx}_{scz}" / "region_meta.json"
        if not region_meta_path.exists():
            self._log(f"!!! [WorldActor] ERROR: Meta file for region ({scx},{scz}) not found. Skipping detailing.")
            return
        with open(region_meta_path, "r", encoding="utf-8") as f:
            meta_data = json.load(f)
            deserialized_road_plan = {}
            road_plan_from_json = meta_data.get("road_plan", {})
            for key_str, plan_dict in road_plan_from_json.items():
                cx_str, cz_str = key_str.split(",")
                chunk_key = (int(cx_str), int(cz_str))
                new_plan = ChunkRoadPlan()
                new_plan.waypoints = [RoadWaypoint(**wp_dict) for wp_dict in plan_dict.get("waypoints", [])]
                deserialized_road_plan[chunk_key] = new_plan
            region_context = Region(
                scx=scx, scz=scz, biome_type="placeholder_biome", road_plan=deserialized_road_plan,
            )
        region_size = self.preset.region_size
        base_cx, base_cz = region_base(scx, scz, region_size)

        for dz in range(region_size):
            for dx in range(region_size):
                chunk_cx, chunk_cz = base_cx + dx, base_cz + dz
                self._log(f"  -> Detailing chunk ({chunk_cx},{chunk_cz})...")
                raw_chunk_path = self.raw_data_path / "chunks" / f"{chunk_cx}_{chunk_cz}.json"
                if not raw_chunk_path.exists():
                    self._log(f"!!! [WorldActor] WARN: Raw chunk file not found for ({chunk_cx},{chunk_cz}). Skipping.")
                    continue

                final_chunk = process_chunk(self.preset, raw_chunk_path, region_context, self.prefab_manager)

                client_chunk_dir = self.final_data_path / f"{chunk_cx}_{chunk_cz}"
                surface_grid = final_chunk.layers.get("surface", [])
                nav_grid = final_chunk.layers.get("navigation", [])
                overlay_grid = final_chunk.layers.get("overlay", [])
                height_grid = final_chunk.layers.get("height_q", {}).get("grid", [])

                if not all([surface_grid, nav_grid, height_grid]):
                    self._log(
                        f"!!! [WorldActor] ERROR: Chunk ({chunk_cx},{chunk_cz}) missing essential layers. Skipping export.")
                    continue

                heightmap_path = client_chunk_dir / "heightmap.r16"
                max_height = float(self.preset.elevation.get("max_height_m", 1.0))
                write_heightmap_r16(str(heightmap_path), height_grid, max_height)

                controlmap_path = client_chunk_dir / "control.r32"
                write_control_map_r32(str(controlmap_path), surface_grid, nav_grid, overlay_grid)

                objects_path = client_chunk_dir / "objects.json"
                placed_objects = getattr(final_chunk, 'placed_objects', [])
                write_objects_json(str(objects_path), placed_objects)

                # Сохраняем navigation.rle.json для сервера
                nav_path = client_chunk_dir / "navigation.rle.json"
                write_navigation_rle(str(nav_path), nav_grid, final_chunk.grid_spec)

                if final_chunk.hex_map_data:
                    server_hex_map_path = client_chunk_dir / "server_hex_map.json"
                    write_server_hex_map(str(server_hex_map_path), final_chunk.hex_map_data)

                preview_path = client_chunk_dir / "preview.png"
                palette = self.preset.export.get("palette", {})
                write_chunk_preview(str(preview_path), surface_grid, nav_grid, palette)

                client_meta_path = client_chunk_dir / "chunk.json"
                contract = ClientChunkContract(cx=chunk_cx, cz=chunk_cz)
                write_client_chunk_meta(str(client_meta_path), contract)