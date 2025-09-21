# ==============================================================================
# Файл: game_engine_restructured/world_actor.py
# ВЕРСИЯ 3.0: Адаптирован для работы с графовыми пресетами.
# ==============================================================================
from __future__ import annotations
import json
from pathlib import Path
from typing import Dict, Any  # <-- ИЗМЕНЕНИЕ: Добавляем типы

# --- Компоненты движка ---
# --- ИЗМЕНЕНИЕ: Убираем Preset, добавляем SimpleNamespace ---
from .core.preset import load_preset  # Оставляем для совместимости
from types import SimpleNamespace

from .core.export import (
    write_client_chunk_meta, write_heightmap_r16,
    write_control_map_r32, write_world_meta_json, write_objects_json,
    read_raw_chunk
)
from .world.processing.detail_processor import DetailProcessor
from .world.context import Region
from .world.road_types import RoadWaypoint, ChunkRoadPlan
from .world.prefab_manager import PrefabManager
from .world.serialization import ClientChunkContract
from .core.export import write_chunk_preview


class WorldActor:
    # --- ИЗМЕНЕНИЕ: Меняем сигнатуру конструктора ---
    def __init__(
            self,
            seed: int,
            # Вместо объекта Preset теперь принимаем словарь с графом
            graph_data: Dict[str, Any],
            artifacts_root: Path,
            # progress_callback=None,
            verbose: bool = False,
    ):
        self.seed = seed
        # --- НОВАЯ ЛОГИКА: Создаем "легкий" пресет на лету ---
        # Это позволяет нам не переписывать весь код ниже,
        # который ожидает объект `preset` с нужными полями.
        self.preset = SimpleNamespace(
            initial_load_radius=graph_data.get("initial_load_radius", 1),
            region_size=graph_data.get("region_size", 3),
            size=graph_data.get("size", 512),
            cell_size=graph_data.get("cell_size", 1.0),
            export=graph_data.get("export", {}),
            # h_norm теперь берется из elevation, если он есть в графе
            h_norm=float(graph_data.get("elevation", {}).get("max_height_m", 800.0)),
            # Сохраняем сам граф для будущей передачи в генератор
            node_graph=graph_data.get("node_graph", {})
        )
        self.graph_data = graph_data # Сохраняем на всякий случай
        # --- КОНЕЦ НОВОЙ ЛОГИКИ ---

        self.artifacts_root = artifacts_root
        self.raw_data_path = self.artifacts_root / "world_raw" / str(self.seed)
        self.final_data_path = self.artifacts_root / "world" / "world_location" / str(self.seed)
        self.progress_callback = progress_callback
        self.verbose = verbose

        prefabs_path = Path(__file__).parent / "data" / "prefabs.json"
        self.prefab_manager = PrefabManager(prefabs_path)
        # Передаем "легкий" пресет дальше
        self.detail_processor = DetailProcessor(self.preset, self.prefab_manager, verbose=self.verbose)
        self.h_norm = self.preset.h_norm # Используем значение из нашего объекта
        if self.verbose:
            print(f"[WorldActor] H_NORM (from graph_data) = {self.h_norm:.3f}")

    def _log(self, message: str):
        if self.progress_callback:
            self.progress_callback(message)

    def prepare_starting_area(self, region_manager):
        radius = self.preset.initial_load_radius
        self._log_progress(0, f"Подготовка области с радиусом {radius}...")

        regions_to_generate = [
            (scx, scz)
            for scz in range(-radius, radius + 1)
            for scx in range(-radius, radius + 1)
        ]
        total_regions = len(regions_to_generate)
        if total_regions == 0:
            self._log_progress(100, "Нет регионов для генерации.")
            return

        for i, (scx, scz) in enumerate(regions_to_generate):
            percent = int((i / total_regions) * 100)
            self._log_progress(percent, f"[{i + 1}/{total_regions}] Обработка региона ({scx}, {scz})...")

            region_manager.generate_raw_region(scx, scz, self.graph_data)
            self._detail_region(scx, scz)

        self._log_progress(100, "Область сгенерирована.")

    def _detail_region(self, scx: int, scz: int):
        # И здесь тоже ничего не меняется
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

    def _log_progress(self, percent: int, message: str):
        if self.progress_callback:
            self.progress_callback(percent, message)
        if self.verbose:
            print(message)

