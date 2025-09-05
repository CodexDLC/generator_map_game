# НОВЫЙ ФАЙЛ: game_engine/world_actor.py
from __future__ import annotations
from pathlib import Path
import json

from .core.preset import Preset
from .core.export import write_client_chunk, write_chunk_preview, write_heightmap_r16, write_color_map_png, \
    write_control_map_png
from .world_structure.grid_utils import region_key, REGION_SIZE
from .world_structure.regions import RegionManager, region_base
from .world_structure.chunk_processor import process_chunk
from .world_structure.context import Region
from .world_structure.road_types import RoadWaypoint, ChunkRoadPlan
from .world_structure.serialization import ClientChunkContract


class WorldActor:
    """
    Главный "дирижер", имитирующий логику сервера.
    Управляет всем процессом генерации.
    """

    def __init__(self, seed: int, preset: Preset, artifacts_root: Path, progress_callback=None):
        self.seed = seed
        self.preset = preset
        self.artifacts_root = artifacts_root
        self.raw_data_path = self.artifacts_root / "world_raw" / str(self.seed)
        self.final_data_path = self.artifacts_root / "world" / "world_location" / str(self.seed)
        # Теперь эта строка корректна, так как progress_callback есть в аргументах
        self.progress_callback = progress_callback


    def _log(self, message: str):
        """Вспомогательная функция для вывода прогресса."""
        if self.progress_callback:
            self.progress_callback(message)

    def ensure_region_is_ready(self, cx: int, cz: int, region_manager: RegionManager):
        scx, scz = region_key(cx, cz)

        # Этап 1: Генерация "сырца"
        region_manager.generate_raw_region(scx, scz)

        final_chunk_path_check = self.final_data_path / f"{cx}_{cz}" / "chunk.rle.json"
        if final_chunk_path_check.exists():
            self._log(f"Final chunks for region ({scx},{scz}) already exist. Skipping detailing.")
            return

        self._log(f"[WorldActor] Detailing required for region ({scx},{scz})...")

        # Этап 2: Детализация
        region_meta_path = self.raw_data_path / "regions" / f"{scx}_{scz}" / "region_meta.json"
        with open(region_meta_path, 'r', encoding='utf-8') as f:
            meta_data = json.load(f)

            # --- НАЧАЛО ИСПРАВЛЕНИЯ: Полная десериализация road_plan ---

            deserialized_road_plan = {}
            # road_plan_from_json - это словарь вида {"-1,0": {"waypoints": [...]}}
            road_plan_from_json = meta_data.get("road_plan", {})

            for key_str, plan_dict in road_plan_from_json.items():
                # Превращаем строку "-1,0" обратно в кортеж (-1, 0)
                cx_str, cz_str = key_str.split(',')
                chunk_key = (int(cx_str), int(cz_str))

                # Создаем пустой объект ChunkRoadPlan
                new_plan = ChunkRoadPlan()
                # Заполняем его вэйпоинтами, создавая объекты RoadWaypoint из словарей
                new_plan.waypoints = [RoadWaypoint(**wp_dict) for wp_dict in plan_dict.get("waypoints", [])]

                deserialized_road_plan[chunk_key] = new_plan

            # --- КОНЕЦ ИСПРАВЛЕНИЯ ---

            region_context = Region(
                scx=scx, scz=scz,
                biome_type="placeholder_biome",
                road_plan=deserialized_road_plan  # <-- Используем полностью восстановленный план
            )

        base_cx, base_cz = region_base(scx, scz)
        total_chunks = REGION_SIZE * REGION_SIZE
        chunk_list = [(dz, dx) for dz in range(REGION_SIZE) for dx in range(REGION_SIZE)]

        for i, (dz, dx) in enumerate(chunk_list):
            chunk_cx, chunk_cz = base_cx + dx, base_cz + dz
            self._log(f"  -> Detailing chunk ({chunk_cx},{chunk_cz}) [{i + 1}/{total_chunks}]...")
            raw_chunk_path = self.raw_data_path / "chunks" / f"{chunk_cx}_{chunk_cz}.json"

            final_chunk = process_chunk(self.preset, raw_chunk_path, region_context)

            # --- НАЧАЛО ИСПРАВЛЕНИЙ ---
            client_chunk_dir = self.final_data_path / f"{chunk_cx}_{chunk_cz}"
            client_rle_path = client_chunk_dir / "chunk.rle.json"
            heightmap_path = client_chunk_dir / "heightmap.r16"  # <-- Путь к нашему файлу
            colormap_path = client_chunk_dir / "colormap.png"
            controlmap_path = client_chunk_dir / "control.png"
            preview_path = client_chunk_dir / "preview.png"

            kind_grid = final_chunk.layers["kind"]
            height_grid = final_chunk.layers["height_q"]["grid"]
            palette = self.preset.export.get("palette", {})

            # Вызываем все функции экспорта
            client_contract = ClientChunkContract(cx=chunk_cx, cz=chunk_cz, layers=final_chunk.layers)
            write_client_chunk(str(client_rle_path), client_contract)

            # ВЫЗЫВАЕМ СОХРАНЕНИЕ КАРТЫ ВЫСОТ
            max_height = float(self.preset.elevation.get("max_height_m", 1.0))
            write_heightmap_r16(str(heightmap_path), height_grid, max_height)

            write_color_map_png(str(colormap_path), kind_grid, palette)
            write_control_map_png(str(controlmap_path), kind_grid)
            write_chunk_preview(str(preview_path), kind_grid, palette)
            # --- КОНЕЦ ИСПРАВЛЕНИЙ ---

        self._log(f"[WorldActor] Detailing for region ({scx},{scz}) is complete.")