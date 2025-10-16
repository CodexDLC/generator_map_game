# ==============================================================================
# Файл: game_engine_restructured/world/processing/region_processor.py
# Назначение: Главный конвейер (pipeline) для обработки одного региона мира.
# ВЕРСИЯ 3.0: Интегрирована новая глобальная климатическая модель.
# ==============================================================================
from __future__ import annotations
import time
from pathlib import Path
from typing import Dict, Tuple, Any
import numpy as np
import json

# --- Базовые компоненты движка ---
from ...core import constants as const
from ...core.preset import Preset
from ...core.types import GenResult
from ...core.export import write_raw_regional_layers

# --- Утилиты и Аналитика ---
from ..grid_utils import _apply_changes_to_chunks, region_base
from ..analytics.region_analysis import RegionAnalysis

# --- "Специалисты" по генерации ---
from ...algorithms.terrain.terrain import generate_elevation_region
from ...algorithms.surfaces import classify_initial_terrain, apply_slope_textures, apply_beach_sand
from ...algorithms.hydrology import apply_sea_level, generate_highland_lakes, generate_rivers

# --- НОВЫЕ ИМПОРТЫ ДЛЯ КЛИМАТА ---
from generator_logic.climate import global_models, biome_matcher
# --- ГЛАВНЫЙ ИМПОРТ НОВОЙ МОДЕЛИ ---
from generator_logic.climate.climate_model import generate_climate_maps
# --- Импортируем функцию для корректного расчета 3D-координат ---
from editor.logic.preview_logic import _generate_world_input


class RegionProcessor:
    def __init__(self, preset: Preset, world_seed: int, artifacts_root: Path):
        self.preset = preset
        self.world_seed = world_seed
        self.artifacts_root = artifacts_root
        self.processed_region_cache: Dict[Tuple[int, int], Dict[str, np.ndarray]] = {}

    def _prepare_context_for_coords(self, scx: int, scz: int, resolution: int, cell_size: float) -> Tuple[Dict, int]:
        """Вспомогательная функция для создания временного контекста для расчета координат."""
        world_side_m = resolution * cell_size
        x_meters = np.linspace(-world_side_m / 2.0, world_side_m / 2.0, resolution, dtype=np.float32)
        z_meters = np.linspace(-world_side_m / 2.0, world_side_m / 2.0, resolution, dtype=np.float32)
        x_coords, z_coords = np.meshgrid(x_meters, z_meters)
        # Простое смещение по сфере для разных регионов.
        # В реальном проекте здесь будет более сложная логика на основе сетки икосаэдра.
        offset_vector = np.array([scx, 0.5, scz], dtype=np.float32)
        offset_vector /= np.linalg.norm(offset_vector)

        context = {
            'WORLD_SIZE_METERS': world_side_m,
            'x_coords': x_coords,
            'z_coords': z_coords,
            'current_world_offset': tuple(offset_vector.tolist())
        }
        return context, resolution

    def process(self, scx: int, scz: int, chunks_with_border: Dict[Tuple[int, int], GenResult]) -> Dict[
        Tuple[int, int], Any]:
        print(f"[RegionProcessor] > Запуск конвейера для региона ({scx}, {scz})...")
        t_start = time.perf_counter()

        # --- БЛОК 0: ПОДГОТОВКА ---
        preset_region_size = self.preset.region_size
        chunk_size = self.preset.size
        ext_size = (preset_region_size + 2) * chunk_size
        scratch_buffers = {
            'a': np.empty((ext_size, ext_size), dtype=np.float32),
            'b': np.empty((ext_size, ext_size), dtype=np.float32)
        }
        biomes_path = Path(__file__).parent.parent.parent / "data" / "biomes.json"
        with open(biomes_path, "r", encoding="utf-8") as f:
            biomes_definition = json.load(f)

        # --- БЛОК 1: РЕЛЬЕФ ---
        stitched_height_ext = generate_elevation_region(
            self.world_seed, scx, scz, preset_region_size, chunk_size, self.preset, scratch_buffers
        )

        # --- БЛОК 2: ТЕКСТУРЫ И ГИДРОЛОГИЯ ---
        stitched_surface_ext = np.empty((ext_size, ext_size), dtype=const.SURFACE_DTYPE)
        stitched_nav_ext = np.empty((ext_size, ext_size), dtype=const.NAV_DTYPE)

        classify_initial_terrain(stitched_surface_ext, stitched_nav_ext)
        is_water_mask = apply_sea_level(stitched_height_ext, stitched_surface_ext, stitched_nav_ext, self.preset)
        generate_highland_lakes(stitched_height_ext, stitched_surface_ext, stitched_nav_ext, None, self.preset,
                                self.world_seed)
        apply_beach_sand(stitched_height_ext, stitched_surface_ext, self.preset)
        apply_slope_textures(stitched_height_ext, stitched_surface_ext, self.preset)
        river_mask_ext = generate_rivers(stitched_height_ext, stitched_surface_ext, stitched_nav_ext, self.preset,
                                         chunk_size)

        # --- БЛОК 3: КЛИМАТ ---
        print("  -> [Climate] Запуск глобальной климатической модели...")

        # 3.1. ИСПРАВЛЕНИЕ БАГА: Генерируем правильные 3D-координаты
        from types import SimpleNamespace
        # Создаем "заглушку" главного окна с необходимыми данными
        mock_main_window = SimpleNamespace(
            current_world_offset=self._get_world_offset_for_region(scx, scz),
            planet_radius_label=SimpleNamespace(text="6371 км"),
        )
        mock_context, _ = self._prepare_context_for_coords(scx, scz, ext_size, self.preset.cell_size)

        # Получаем реальные 3D-координаты точек региона на сфере
        region_coords_3d = _generate_world_input(mock_main_window, mock_context, {}, return_coords_only=True)

        # 3.2. Расчет глобальной температуры
        temp_params = self.preset.climate.get("temperature", {})
        base_temp_map = global_models.calculate_base_temperature(
            xyz_coords=region_coords_3d.reshape(-1, 3),
            base_temp_c=temp_params.get("base_c", 15.0),
            equator_pole_temp_diff_c=temp_params.get("equator_pole_diff", 30.0)
        ).reshape((ext_size, ext_size))

        temperature_map = base_temp_map + stitched_height_ext * temp_params.get("lapse_rate_c_per_m", -0.0065)

        # 3.3. Вызов нового оркестратора для расчета влажности
        climate_context = {
            "height_map": stitched_height_ext,
            "is_water_mask": is_water_mask,
            "river_mask": river_mask_ext,
            "temperature_map": temperature_map,
            "cell_size_m": self.preset.cell_size,
            "climate_params": self.preset.climate.get("humidity", {})
        }
        climate_data = generate_climate_maps(climate_context)
        humidity_map = climate_data.get('humidity', np.full_like(temperature_map, 0.5))

        stitched_layers_ext = {
            'height': stitched_height_ext, 'surface': stitched_surface_ext,
            'navigation': stitched_nav_ext, 'river': river_mask_ext,
            'temperature': temperature_map, 'humidity': humidity_map,
            'shadow': climate_data.get('rain_shadow', np.zeros_like(humidity_map))
        }

        # 3.4. Расчет биомов
        core_slice = slice(chunk_size, -chunk_size)
        avg_temp = float(np.mean(temperature_map[core_slice, core_slice]))
        avg_humidity = float(np.mean(humidity_map[core_slice, core_slice]))
        biome_probabilities = biome_matcher.calculate_biome_probabilities(avg_temp, avg_humidity, biomes_definition)

        # --- БЛОК 4: АНАЛИТИКА И ЗАВЕРШЕНИЕ ---
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
                          if k in ['temperature', 'humidity']}
        if layers_to_save:
            write_raw_regional_layers(str(region_raw_path / "climate_layers.npz"), layers_to_save, verbose=True)

        base_cx, base_cz = region_base(scx, scz, preset_region_size)
        final_chunks_for_region = {
            k: v for k, v in chunks_with_border.items()
            if base_cx <= k[0] < base_cx + preset_region_size and base_cz <= k[1] < base_cz + preset_region_size
        }

        _apply_changes_to_chunks(stitched_layers_ext, final_chunks_for_region, base_cx, base_cz, chunk_size)

        print(
            f"[RegionProcessor] < Конвейер для региона ({scx}, {scz}) завершен. Время: {(time.perf_counter() - t_start) * 1000:.2f} мс")

        return {
            "processed_chunks": final_chunks_for_region,
            "biome_probabilities": biome_probabilities
        }

    def _get_world_offset_for_region(self, scx: int, scz: int) -> tuple[float, float, float]:
        # Простая функция для получения вектора смещения на сфере.
        # В реальной системе здесь была бы логика на основе икосаэдра.
        angle_x = scx * 0.1  # Примерное смещение
        angle_z = scz * 0.1

        # Простое вращение вокруг осей Y и X
        x = np.cos(angle_x) * np.cos(angle_z)
        y = np.sin(angle_z)
        z = np.sin(angle_x) * np.cos(angle_z)

        vec = np.array([x, y, z])
        return tuple((vec / np.linalg.norm(vec)).tolist())