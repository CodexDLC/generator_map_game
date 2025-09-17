# ==============================================================================
# Файл: game_engine_restructured/world_actor.py
# Назначение: Главный "оркестратор", который управляет всем процессом
#             генерации мира от начала до конца.
# ==============================================================================
from __future__ import annotations
import json
from pathlib import Path

# --- Компоненты движка ---
from .core.preset import Preset
from .core.export import (
    write_client_chunk_meta, write_chunk_preview, write_heightmap_r16,
    write_control_map_r32, write_world_meta_json, write_objects_json,
    write_navigation_rle, read_raw_chunk
)
from .world.grid_utils import region_base
from .world.regions import RegionManager
from .world.processing.detail_processor import DetailProcessor
from .world.context import Region
from .world.road_types import RoadWaypoint, ChunkRoadPlan
from .world.prefab_manager import PrefabManager
from .world.serialization import ClientChunkContract
from .algorithms.terrain.terrain_helpers import compute_amp_sum

class WorldActor:
    """
    Отвечает за высокоуровневую логику генерации:
    - Определяет, какие регионы нужно сгенерировать.
    - Вызывает RegionManager для создания "сырых" данных.
    - Вызывает DetailProcessor для добавления деталей (дороги, леса).
    - Вызывает экспортеры для сохранения финальных файлов для Godot.
    """

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

        # --- Инициализация "специалистов" ---
        prefabs_path = Path(__file__).parent / "data" / "prefabs.json"
        self.prefab_manager = PrefabManager(prefabs_path)
        self.detail_processor = DetailProcessor(preset, self.prefab_manager)
        self.h_norm = compute_amp_sum(self.preset)
        if self.verbose:
            print(f"[WorldActor] H_NORM (sum of amp_m) = {self.h_norm:.3f}")

    def _log(self, message: str):
        """Вспомогательная функция для логирования."""
        if self.progress_callback:
            self.progress_callback(message)

    def prepare_starting_area(self, region_manager: RegionManager):
        """
        Главный метод, запускающий генерацию стартовой области.
        """
        radius = self.preset.initial_load_radius
        self._log(f"\n[WorldActor] Preparing start area with REGION radius {radius}...")

        regions_to_generate = [
            (scx, scz)
            for scz in range(-radius, radius + 1)
            for scx in range(-radius, radius + 1)
        ]
        total_regions = len(regions_to_generate)
        self._log(f"[WorldActor] Found {total_regions} regions to generate.")

        for i, (scx, scz) in enumerate(regions_to_generate):
            self._log(f"\n--- [{i + 1}/{total_regions}] Processing Region ({scx}, {scz}) ---")
            # 1. Генерируем "сырой" регион (рельеф, климат, базовые текстуры)
            region_manager.generate_raw_region(scx, scz)
            # 2. Добавляем детали и сохраняем финальные файлы для Godot
            self._detail_region(scx, scz)

    def _detail_region(self, scx: int, scz: int):
        """
        Обрабатывает один регион: читает сырые чанки, добавляет детали
        (дороги, леса) и экспортирует их в финальный формат.
        """
        self._log(f"[WorldActor] Detailing required for region ({scx},{scz})...")

        # --- Загрузка метаданных региона ---
        region_meta_path = self.raw_data_path / "regions" / f"{scx}_{scz}" / "region_meta.json"
        if not region_meta_path.exists():
            self._log(f"!!! [WorldActor] ERROR: Meta file for region ({scx},{scz}) not found. Skipping detailing.")
            return

        with open(region_meta_path, "r", encoding="utf-8") as f:
            meta_data = json.load(f)
            # Десериализация планов дорог
            road_plan = {
                tuple(map(int, k.split(','))): ChunkRoadPlan(
                    waypoints=[RoadWaypoint(**wp) for wp in v.get("waypoints", [])]
                )
                for k, v in meta_data.get("road_plan", {}).items()
            }
            region_context = Region(scx=scx, scz=scz, biome_type="placeholder_biome", road_plan=road_plan)

        # --- Обработка каждого чанка в регионе ---
        region_size = self.preset.region_size
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
                overlay_grid = final_chunk.layers.get("overlay")
                height_grid = final_chunk.layers.get("height_q", {}).get("grid", [])

                if surface_grid is None or surface_grid.size == 0 or not height_grid:
                    self._log(
                        f"!!! [WorldActor] ERROR: Chunk ({chunk_cx},{chunk_cz}) missing essential layers. Skipping export.")
                    continue



                # Читаем настройки логирования из пресета
                log_stats = self.preset.export.get("log_chunk_stats", False)
                log_saves = self.preset.export.get("log_file_saves", False)

                # Вызываем функции экспорта с правильными флагами
                write_heightmap_r16(str(client_chunk_dir / "heightmap.r16"),
                                    height_grid,
                                    h_norm=self.h_norm,
                                    verbose=log_saves)

                from collections import Counter
                surface_counts = Counter(surface_grid.flatten())
                print(f"Surface grid stats before export: {surface_counts}")

                write_control_map_r32(str(client_chunk_dir / "control.r32"), surface_grid, nav_grid, overlay_grid,
                                      verbose=log_stats)
                write_objects_json(str(client_chunk_dir / "objects.json"), getattr(final_chunk, "placed_objects", []),
                                   verbose=log_saves)
                write_navigation_rle(str(client_chunk_dir / "navigation.rle.json"), nav_grid, final_chunk.grid_spec,
                                     verbose=log_saves)
                write_chunk_preview(str(client_chunk_dir / "preview.png"), surface_grid, nav_grid,
                                    self.preset.export.get("palette", {}), verbose=log_saves)
                write_client_chunk_meta(str(client_chunk_dir / "chunk.json"),
                                        ClientChunkContract(cx=chunk_cx, cz=chunk_cz), verbose=log_saves)