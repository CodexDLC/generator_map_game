# НОВЫЙ ФАЙЛ: game_engine/world_actor.py
from __future__ import annotations
from pathlib import Path
import json

from .core.preset import Preset
from .core.export import write_client_chunk, write_chunk_preview
from .world_structure.grid_utils import region_key, REGION_SIZE
from .world_structure.regions import RegionManager, region_base
from .world_structure.chunk_processor import process_chunk
from .world_structure.context import Region
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

        # Проверяем, нужно ли детализировать
        final_chunk_path_check = self.final_data_path / f"{cx}_{cz}" / "chunk.rle.json"
        if final_chunk_path_check.exists():
            self._log(f"Final chunks for region ({scx},{scz}) already exist. Skipping detailing.")
            return

        self._log(f"[WorldActor] Detailing required for region ({scx},{scz})...")

        # Этап 2: Детализация
        region_meta_path = self.raw_data_path / "regions" / f"{scx}_{scz}" / "region_meta.json"
        with open(region_meta_path, 'r', encoding='utf-8') as f:
            meta_data = json.load(f)
            road_plan_str_keys = meta_data.get("road_plan", {})
            road_plan = {tuple(eval(k.replace('__tuple__', ''))): v for k, v in road_plan_str_keys.items()}

            region_context = Region(
                scx=scx, scz=scz,
                biome_type="placeholder_biome",
                road_plan=road_plan
            )

        base_cx, base_cz = region_base(scx, scz)
        total_chunks = REGION_SIZE * REGION_SIZE
        chunk_list = [(dz, dx) for dz in range(REGION_SIZE) for dx in range(REGION_SIZE)]

        for i, (dz, dx) in enumerate(chunk_list):
            chunk_cx, chunk_cz = base_cx + dx, base_cz + dz

            self._log(f"  -> Detailing chunk ({chunk_cx},{chunk_cz}) [{i + 1}/{total_chunks}]...")

            raw_chunk_path = self.raw_data_path / "chunks" / f"{chunk_cx}_{chunk_cz}.json"
            final_chunk = process_chunk(self.preset, raw_chunk_path, region_context)

            client_chunk_path = self.final_data_path / f"{chunk_cx}_{chunk_cz}" / "chunk.rle.json"
            client_contract = ClientChunkContract(cx=chunk_cx, cz=chunk_cz, layers=final_chunk.layers)
            write_client_chunk(str(client_chunk_path), client_contract)

            preview_path = client_chunk_path.parent / "preview.png"
            palette = self.preset.export.get("palette", {})
            write_chunk_preview(str(preview_path), final_chunk.layers["kind"], palette)

        self._log(f"[WorldActor] Detailing for region ({scx},{scz}) is complete.")