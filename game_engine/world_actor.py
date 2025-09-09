# Файл: game_engine/world_actor.py
from __future__ import annotations
import os
from pathlib import Path
import json

from .core.grid.hex import HexGridSpec
from .core.preset import Preset
# --- ИЗМЕНЕНИЕ: Обновляем импорты ---
from .core.export import (
    write_client_chunk_meta,
    write_chunk_preview,
    write_heightmap_r16,
    write_control_map_r32,
    write_world_meta_json,
    write_objects_json, write_navigation_rle
)
from .world_structure.grid_utils import region_key, region_base
from .world_structure.regions import RegionManager
from .world_structure.chunk_processor import process_chunk
from .world_structure.context import Region
from .world_structure.road_types import RoadWaypoint, ChunkRoadPlan
# --- НОВЫЕ ИМПОРТЫ ---
from .world_structure.prefab_manager import PrefabManager
from .world_structure.serialization import ClientChunkContract


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

        # --- ДОБАВЛЕНО: Загружаем каталог префабов при старте ---
        prefabs_path = Path(__file__).parent / "prefabs.json"
        self.prefab_manager = PrefabManager(prefabs_path)

    def _log(self, message: str):
        if self.progress_callback:
            self.progress_callback(message)

    def prepare_starting_area(self, region_manager: RegionManager):
        """
        Генерирует все регионы в пределах стартового радиуса, указанного в пресете.
        """
        # --- ИЗМЕНЕНИЕ: Теперь мы используем радиус для обхода РЕГИОНОВ, а не чанков ---
        radius = self.preset.initial_load_radius
        print(f"\n[WorldActor] Preparing start area with REGION radius {radius}...")

        # 1. Создаем список всех регионов, которые нужно сгенерировать
        regions_to_generate = []
        for scz in range(-radius, radius + 1):
            for scx in range(-radius, radius + 1):
                regions_to_generate.append((scx, scz))

        total_regions = len(regions_to_generate)
        print(f"[WorldActor] Found {total_regions} regions to generate.")

        # 2. Последовательно генерируем и детализируем каждый регион из списка
        for i, (scx, scz) in enumerate(regions_to_generate):
            print(f"\n--- [{i + 1}/{total_regions}] Processing Region ({scx}, {scz}) ---")
            # Сначала генерируем "сырые" данные (карты высот, базовый рельеф)
            region_manager.generate_raw_region(scx, scz)
            # Затем применяем детализацию (дороги, биомы и т.д.)
            self._detail_region(scx, scz)

    def _detail_region(self, scx: int, scz: int):

        # (код загрузки region_meta.json и road_plan без изменений)
        WORLD_ID = "world_location"
        meta_path = str(self.final_data_path.parent / "_world_meta.json")
        if not os.path.exists(meta_path):
            write_world_meta_json(
                meta_path, world_id=WORLD_ID, hex_edge_m=0.63, meters_per_pixel=0.25,
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

                # --- ИЗМЕНЕНИЕ: Передаем prefab_manager в process_chunk ---
                final_chunk = process_chunk(self.preset, raw_chunk_path, region_context, self.prefab_manager)

                # --- ЭТАП ЭКСПОРТА В ФИНАЛЬНЫЙ ФОРМАТ ---
                client_chunk_dir = self.final_data_path / f"{chunk_cx}_{chunk_cz}"

                # Получаем данные слоев
                surface_grid = final_chunk.layers.get("surface", [])
                nav_grid = final_chunk.layers.get("navigation", [])
                overlay_grid = final_chunk.layers.get("overlay", [])
                height_grid = final_chunk.layers.get("height_q", {}).get("grid", [])

                if not all([surface_grid, nav_grid, height_grid]):
                    self._log(
                        f"!!! [WorldActor] ERROR: Chunk ({chunk_cx},{chunk_cz}) missing essential layers. Skipping export.")
                    continue

                # 1. Сохраняем heightmap.r16
                heightmap_path = client_chunk_dir / "heightmap.r16"
                max_height = float(self.preset.elevation.get("max_height_m", 1.0))
                write_heightmap_r16(str(heightmap_path), height_grid, max_height)

                # 2. Сохраняем control.r32
                controlmap_path = client_chunk_dir / "control.r32"
                write_control_map_r32(str(controlmap_path), surface_grid, nav_grid, overlay_grid)

                # 3. Сохраняем objects.json (пока будет пустым, так как кисти отключены)
                objects_path = client_chunk_dir / "objects.json"
                placed_objects = getattr(final_chunk, 'placed_objects', [])
                write_objects_json(str(objects_path), placed_objects)

                # --- VVV ДОБАВЬТЕ ЭТОТ БЛОК VVV ---
                # 4. Сохраняем navigation.rle.json для сервера
                nav_path = client_chunk_dir / "navigation.rle.json"
                write_navigation_rle(str(nav_path), nav_grid)
                # --- ^^^ КОНЕЦ НОВОГО БЛОКА ^^^ ---

                # 5. Сохраняем preview.png для тестера (теперь это пункт 5)
                preview_path = client_chunk_dir / "preview.png"
                palette = self.preset.export.get("palette", {})
                write_chunk_preview(str(preview_path), surface_grid, nav_grid, palette)

                # 6. Сохраняем главный chunk.json (теперь это пункт 6)
                client_meta_path = client_chunk_dir / "chunk.json"
                contract = ClientChunkContract(cx=chunk_cx, cz=chunk_cz)
                write_client_chunk_meta(str(client_meta_path), contract)