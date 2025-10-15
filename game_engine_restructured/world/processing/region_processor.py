# ==============================================================================
# Файл: game_engine_restructured/world/processing/region_processor.py
# Назначение: Главный конвейер (pipeline) для обработки одного региона мира.
# ВЕРСИЯ 2.0: Интегрирована глобальная климатическая модель.
# ==============================================================================
from __future__ import annotations
import time
from pathlib import Path
from typing import Dict, Tuple, Any
import numpy as np
import json  # <-- ДОБАВЛЕН ИМПОРТ

# --- Базовые компоненты движка ---
from ...core import constants as const
from ...core.preset import Preset
from ...core.types import GenResult
from ...core.export import write_raw_regional_layers

# --- Утилиты и Аналитика ---
from ..grid_utils import _apply_changes_to_chunks, region_base
from ..analytics.region_analysis import RegionAnalysis

# --- "Специалисты" по генерации (каждый отвечает за свою задачу) ---
from ...algorithms.terrain.terrain import generate_elevation_region
from ...algorithms.surfaces import classify_initial_terrain, apply_slope_textures, apply_beach_sand
from ...algorithms.hydrology import apply_sea_level, generate_highland_lakes, generate_rivers

# --- НОВЫЕ ИМПОРТЫ ДЛЯ КЛИМАТА ---
from generator_logic.climate import global_models, local_effects, biome_matcher


class RegionProcessor:
    def __init__(self, preset: Preset, world_seed: int, artifacts_root: Path):
        self.preset = preset
        self.world_seed = world_seed
        self.artifacts_root = artifacts_root
        # Кэш для хранения ключевых данных регионов (используется для анализа швов)
        self.processed_region_cache: Dict[Tuple[int, int], Dict[str, np.ndarray]] = {}

    def process(self, scx: int, scz: int, chunks_with_border: Dict[Tuple[int, int], GenResult]) -> Dict[
        Tuple[int, int], Any]:
        """
        Основной метод, запускающий полный цикл обработки региона.
        ВЕРСИЯ 2.0: Интегрирована глобальная климатическая модель.
        """
        print(f"[RegionProcessor] > Запуск конвейера для региона ({scx}, {scz})...")
        t_start = time.perf_counter()

        # ======================================================================
        # --- БЛОК 0: ПОДГОТОВКА ДАННЫХ ---
        # ======================================================================
        preset_region_size = self.preset.region_size
        chunk_size = self.preset.size
        ext_size = (preset_region_size + 2) * chunk_size
        scratch_buffers = {
            'a': np.empty((ext_size, ext_size), dtype=np.float32),
            'b': np.empty((ext_size, ext_size), dtype=np.float32)
        }

        # Загружаем справочник биомов
        biomes_path = Path(__file__).parent.parent.parent / "data" / "biomes.json"
        with open(biomes_path, "r", encoding="utf-8") as f:
            biomes_definition = json.load(f)

        # ======================================================================
        # --- БЛОК 1: ГЕНЕРАЦИЯ РЕЛЬЕФА (ELEVATION) ---
        # ======================================================================
        stitched_height_ext = generate_elevation_region(
            self.world_seed, scx, scz, preset_region_size, chunk_size, self.preset, scratch_buffers
        )

        # ======================================================================
        # --- БЛОК 2: ТЕКСТУРИРОВАНИЕ И ГИДРОЛОГИЯ ---
        # ======================================================================
        stitched_surface_ext = np.empty((ext_size, ext_size), dtype=const.SURFACE_DTYPE)
        stitched_nav_ext = np.empty((ext_size, ext_size), dtype=const.NAV_DTYPE)

        classify_initial_terrain(stitched_surface_ext, stitched_nav_ext)
        generate_highland_lakes(
            stitched_height_ext, stitched_surface_ext, stitched_nav_ext,
            None, self.preset, self.world_seed
        )
        apply_sea_level(stitched_height_ext, stitched_surface_ext, stitched_nav_ext, self.preset)
        apply_beach_sand(stitched_height_ext, stitched_surface_ext, self.preset)
        apply_slope_textures(stitched_height_ext, stitched_surface_ext, self.preset)
        river_mask_ext = generate_rivers(
            stitched_height_ext, stitched_surface_ext, stitched_nav_ext, self.preset, chunk_size
        )

        # ======================================================================
        # --- БЛОК 3: ГЕНЕРАЦИЯ КЛИМАТА (НОВАЯ ЛОГИКА) ---
        # ======================================================================
        print("  -> [Climate] Запуск глобальной климатической модели...")
        stitched_layers_ext = {
            'height': stitched_height_ext,
            'surface': stitched_surface_ext,
            'navigation': stitched_nav_ext,
            'river': river_mask_ext
        }

        # 3.1. Получаем 3D координаты для текущего региона (пока заглушка)
        region_coords_3d = np.random.rand(ext_size * ext_size, 3).astype(np.float32) * 2 - 1

        # 3.2. Рассчитываем глобальную температуру
        # TODO: Заменить хардкод на параметры из UI
        base_temp_map = global_models.calculate_base_temperature(
            xyz_coords=region_coords_3d,
            base_temp_c=15.0,
            equator_pole_temp_diff_c=30.0
        ).reshape((ext_size, ext_size))

        # 3.3. Добавляем локальное влияние высоты на температуру
        lapse_rate = -0.0065  # °C на метр
        temperature_map = base_temp_map + stitched_height_ext * lapse_rate

        # 3.4. Рассчитываем глобальную влажность (пока простой шум)
        # TODO: Заменить на симуляцию ветров и переноса влаги
        humidity_map = np.random.rand(ext_size, ext_size).astype(np.float32) * 0.5 + 0.2

        # 3.5. Вычисляем средние показатели для региона
        core_slice = slice(chunk_size, -chunk_size)
        avg_temp = float(np.mean(temperature_map[core_slice, core_slice]))
        avg_humidity = float(np.mean(humidity_map[core_slice, core_slice]))

        print(f"    -> Средние показатели региона: t={avg_temp:.1f}°C, влажность={avg_humidity:.2f}")

        # 3.6. Рассчитываем вероятности биомов
        biome_probabilities = biome_matcher.calculate_biome_probabilities(
            avg_temp_c=avg_temp,
            avg_humidity=avg_humidity,
            biomes_definition=biomes_definition
        )
        print(f"    -> Вероятности биомов: {biome_probabilities}")

        stitched_layers_ext['temperature'] = temperature_map
        stitched_layers_ext['humidity'] = humidity_map

        # ======================================================================
        # --- БЛОК 4: АНАЛИТИКА, НАРЕЗКА И СОХРАНЕНИЕ ---
        # ======================================================================
        analysis = RegionAnalysis(scx, scz, stitched_layers_ext, chunk_size)
        neighbor_data = {
            "north": self.processed_region_cache.get((scx, scz - 1)),
            "west": self.processed_region_cache.get((scx - 1, scz)),
        }
        analysis.run(neighbor_data)
        analysis.print_report()
        self.processed_region_cache[(scx, scz)] = analysis.layers_core.copy()

        region_raw_path = self.artifacts_root / "world_raw" / str(self.world_seed) / "regions" / f"{scx}_{scz}"
        layers_to_save = {k: v for k, v in analysis.layers_core.items()
                          if k in ['temperature', 'humidity']}  # Сохраняем только то, что сгенерировали
        if layers_to_save:
            write_raw_regional_layers(str(region_raw_path / "climate_layers.npz"), layers_to_save, verbose=True)

        base_cx, base_cz = region_base(scx, scz, preset_region_size)
        final_chunks_for_region = {
            k: v for k, v in chunks_with_border.items()
            if base_cx <= k[0] < base_cx + preset_region_size and base_cz <= k[1] < base_cz + preset_region_size
        }

        _apply_changes_to_chunks(analysis.layers_core, final_chunks_for_region, base_cx, base_cz, chunk_size)

        print(
            f"[RegionProcessor] < Конвейер для региона ({scx}, {scz}) завершен. Время: {(time.perf_counter() - t_start) * 1000:.2f} мс")

        return {
            "processed_chunks": final_chunks_for_region,
            "biome_probabilities": biome_probabilities
        }