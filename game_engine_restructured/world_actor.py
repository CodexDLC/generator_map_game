# ==============================================================================
# Файл: game_engine_restructured/world_actor.py
# ВЕРСИЯ 2.0: Исправлен критический импорт DetailProcessor.
# ==============================================================================
from __future__ import annotations
import json
from pathlib import Path

# --- Компоненты движка ---
from .core.preset import Preset
from .core.export import (
    write_client_chunk_meta, write_heightmap_r16,
    write_control_map_r32, write_world_meta_json, write_objects_json,
    read_raw_chunk
)
# --- НАЧАЛО ИСПРАВЛЕНИЯ: Неправильный импорт ---
from .world.processing.detail_processor import DetailProcessor
# --- КОНЕЦ ИСПРАВЛЕНИЯ ---
from .world.context import Region
from .world.road_types import RoadWaypoint, ChunkRoadPlan
from .world.prefab_manager import PrefabManager
from .world.serialization import ClientChunkContract


# --- НАЧАЛО ИСПРАВЛЕНИЯ: Отсутствующий импорт ---
from .core.export import write_chunk_preview
# --- КОНЕЦ ИСПРАВЛЕНИЯ ---


class WorldActor:
    def __init__(
            self,
            seed: int,
            preset: Preset,
            artifacts_root: Path,
            progress_callback=None,
            verbose: bool = False,
    ):
        self.seed = seed
        self.preset = preset
        self.artifacts_root = artifacts_root
        self.raw_data_path = self.artifacts_root / "world_raw" / str(self.seed)
        self.final_data_path = self.artifacts_root / "world" / "world_location" / str(self.seed)
        self.progress_callback = progress_callback
        self.verbose = verbose

        prefabs_path = Path(__file__).parent / "data" / "prefabs.json"
        self.prefab_manager = PrefabManager(prefabs_path)
        self.detail_processor = DetailProcessor(preset, self.prefab_manager, verbose=self.verbose)
        self.h_norm = float(self.preset.elevation.get("max_height_m", 1.0))
        if self.verbose:
            # Обновляем сообщение для ясности
            print(f"[WorldActor] H_NORM (from preset max_height_m) = {self.h_norm:.3f}")

    def _log(self, message: str):
        if self.progress_callback:
            self.progress_callback(message)

    def prepare_starting_area(self, region_manager):
        radius = self.preset.initial_load_radius
        self._log(f"\n[WorldActor] Preparing start area with REGION radius {radius}...")

        regions_to_generate = [
            (scx, scz)
            for scz in range(-radius, radius + 1)
            for scx in range(-radius, radius + 1)
        ]
        total_regions = len(regions_to_generate)

        for i, (scx, scz) in enumerate(regions_to_generate):
            self._log(f"\n--- [{i + 1}/{total_regions}] Processing Region ({scx}, {scz}) ---")
            region_manager.generate_raw_region(scx, scz)
            self._detail_region(scx, scz)

    def _detail_region(self, scx: int, scz: int):
        self._log(f"[WorldActor] Detailing required for region ({scx},{scz})...")

        region_meta_path = self.raw_data_path / "regions" / f"{scx}_{scz}" / "region_meta.json"
        if not region_meta_path.exists():
            return

        with open(region_meta_path, "r", encoding="utf-8") as f:
            meta_data = json.load(f)
            road_plan = {
                tuple(map(int, k.split(','))): ChunkRoadPlan(
                    waypoints=[RoadWaypoint(**wp) for wp in v.get("waypoints", [])]
                )
                for k, v in meta_data.get("road_plan", {}).items()
            }
            region_context = Region(scx=scx, scz=scz, biome_type="placeholder_biome", road_plan=road_plan)

        region_size = self.preset.region_size
        from .world.grid_utils import region_base
        base_cx, base_cz = region_base(scx, scz, region_size)

        for dz in range(region_size):
            for dx in range(region_size):
                chunk_cx, chunk_cz = base_cx + dx, base_cz + dz
                path_prefix = str(self.raw_data_path / "chunks" / f"{chunk_cx}_{chunk_cz}")
                chunk_for_detailing = read_raw_chunk(path_prefix)
                if not chunk_for_detailing:
                    continue

                final_chunk = self.detail_processor.process(chunk_for_detailing, region_context)
                client_chunk_dir = self.final_data_path / f"{chunk_cx}_{chunk_cz}"
                surface_grid = final_chunk.layers.get("surface")
                nav_grid = final_chunk.layers.get("navigation")
                height_grid = final_chunk.layers.get("height_q", {}).get("grid", [])

                if surface_grid is None or not height_grid:
                    continue

                log_saves = self.preset.export.get("log_file_saves", False)
                write_heightmap_r16(str(client_chunk_dir / "heightmap.r16"), height_grid, h_norm=self.h_norm, verbose=log_saves)
                write_control_map_r32(str(client_chunk_dir / "control.r32"), surface_grid, nav_grid, final_chunk.layers.get("overlay"), verbose=log_saves)
                write_objects_json(str(client_chunk_dir / "objects.json"), getattr(final_chunk, "placed_objects", []), verbose=log_saves)
                write_chunk_preview(str(client_chunk_dir / "preview.png"), surface_grid, nav_grid, self.preset.export.get("palette", {}), verbose=log_saves)
                write_client_chunk_meta(str(client_chunk_dir / "chunk.json"), ClientChunkContract(cx=chunk_cx, cz=chunk_cz), verbose=log_saves)