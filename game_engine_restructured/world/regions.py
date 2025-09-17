# ==============================================================================
# Файл: game_engine_restructured/world/regions.py
# Назначение: Управляет процессом генерации на уровне регионов.
#             Координирует создание "пустых" чанков-контейнеров и вызывает
#             RegionProcessor для их пакетного заполнения.
# ВЕРСИЯ 3.0: BaseProcessor полностью удален из конвейера.
# ==============================================================================
from __future__ import annotations
import concurrent.futures
from pathlib import Path
from typing import Dict, Tuple

# --- Компоненты движка ---
from ..core.preset import Preset
from ..core.types import GenResult, HexGridSpec
from ..core.export import write_region_meta, write_raw_chunk
from .processing.region_processor import RegionProcessor
from .serialization import RegionMetaContract
from ..core.utils.rng import init_rng
from ..core.utils.layers import make_empty_layers
from .planners.road_planner import plan_roads_for_region
from .grid_utils import region_base

class RegionManager:
    def __init__(self, world_seed: int, preset: Preset, artifacts_root: Path):
        self.world_seed = world_seed
        self.preset = preset
        self.artifacts_root = artifacts_root
        self.raw_data_path = self.artifacts_root / "world_raw" / str(self.world_seed)
        # RegionProcessor - единственный обработчик, который нам нужен
        self.region_processor = RegionProcessor(preset, world_seed, self.artifacts_root)
        self.base_chunk_cache: Dict[Tuple[int, int], GenResult] = {}

    def _generate_or_get_chunk_task(self, cx: int, cz: int) -> GenResult:
        """
        Задача для одного потока: СОЗДАТЬ ПУСТОЙ КОНТЕЙНЕР ДЛЯ ЧАНКА.
        Генерация данных будет выполнена позже пакетно в RegionProcessor.
        """
        if (cx, cz) in self.base_chunk_cache:
            return self.base_chunk_cache[(cx, cz)]

        size = self.preset.size
        grid_spec = HexGridSpec(
            edge_m=0.63, meters_per_pixel=float(self.preset.cell_size), chunk_px=size
        )
        stage_seeds = init_rng(self.world_seed, cx, cz)

        # Создаем пустой результат. Слои будут заполнены позже в RegionProcessor.
        chunk_result = GenResult(
            version="chunk_v2_regional",
            type="world_chunk_base",
            seed=self.world_seed,
            cx=cx,
            cz=cz,
            size=size,
            cell_size=float(self.preset.cell_size),
            layers=make_empty_layers(size),  # Создаем пустые слои-заглушки
            stage_seeds=stage_seeds,
            grid_spec=grid_spec,
        )

        self.base_chunk_cache[(cx, cz)] = chunk_result
        return chunk_result

    def generate_raw_region(self, scx: int, scz: int):
        """
        Основной метод, который генерирует все "сырые" данные для одного региона.
        """
        region_meta_path = (
                self.raw_data_path / "regions" / f"{scx}_{scz}" / "region_meta.json"
        )
        if region_meta_path.exists():
            print(f"[RegionManager] Сырые данные для региона ({scx},{scz}) уже существуют.")
            return

        print(f"[RegionManager] > Запуск генерации сырых данных для региона ({scx}, {scz})...")

        region_size = self.preset.region_size
        base_cx, base_cz = region_base(scx, scz, region_size)

        # Собираем задачи на создание чанков, включая одночанковую границу ("фартук").
        tasks = []
        for dz in range(-1, region_size + 1):
            for dx in range(-1, region_size + 1):
                tasks.append((base_cx + dx, base_cz + dz))

        chunks_with_border: Dict[Tuple[int, int], GenResult] = {}
        # Используем многопоточность для ускорения создания пустых контейнеров.
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future_to_chunk = {
                executor.submit(self._generate_or_get_chunk_task, cx, cz): (cx, cz)
                for cx, cz in tasks
            }
            for future in concurrent.futures.as_completed(future_to_chunk):
                try:
                    chunk_result = future.result()
                    key = (chunk_result.cx, chunk_result.cz)
                    chunks_with_border[key] = chunk_result
                except Exception as exc:
                    print(f"!!! Ошибка при создании контейнера чанка: {exc}")

        print(
            f"  -> Создано {len(chunks_with_border)} пустых контейнеров для чанков (с границей)."
        )

        # Передаем пустые контейнеры в RegionProcessor для основной пакетной обработки.
        processed_chunks = self.region_processor.process(scx, scz, chunks_with_border)

        # Отбираем только те чанки, которые относятся к "ядру" региона.
        final_chunks_for_region = {
            k: v
            for k, v in processed_chunks.items()
            if base_cx <= k[0] < base_cx + region_size
               and base_cz <= k[1] < base_cz + region_size
        }

        # --- Планировщики (дороги и т.д.) работают уже с полностью обработанными данными ---
        road_plan = plan_roads_for_region(
            scx, scz, self.world_seed, self.preset, final_chunks_for_region
        )

        # Сохраняем мета-файл региона с планом дорог.
        meta_contract = RegionMetaContract(
            scx=scx,
            scz=scz,
            world_seed=self.world_seed,
            road_plan=road_plan,
        )
        write_region_meta(str(region_meta_path), meta_contract)

        # Сохраняем "сырые" данные каждого чанка региона.
        for (cx, cz), chunk_data in final_chunks_for_region.items():
            path_prefix = str(self.raw_data_path / "chunks" / f"{cx}_{cz}")
            write_raw_chunk(path_prefix, chunk_data)

        print(f"[RegionManager] < Генерация сырых данных для региона ({scx}, {scz}) завершена.")