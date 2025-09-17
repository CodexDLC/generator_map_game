# ==============================================================================
# Файл: game_engine_restructured/world/processing/region_processor.py
# Назначение: Главный конвейер (pipeline) для обработки одного региона мира.
#             Отвечает за последовательный вызов всех этапов генерации:
#             рельеф, климат, текстуры, вода, аналитика и сохранение.
# ==============================================================================
from __future__ import annotations
import time
from pathlib import Path
from typing import Dict, Tuple
import numpy as np

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
from ...algorithms.climate.climate import generate_climate_maps
# --- ИСПРАВЛЕННЫЕ ИМПОРТЫ ---
from ...algorithms.surfaces import classify_initial_terrain, apply_slope_textures, apply_beach_sand
from ...algorithms.hydrology import apply_sea_level, generate_highland_lakes, generate_rivers


class RegionProcessor:
    def __init__(self, preset: Preset, world_seed: int, artifacts_root: Path):
        self.preset = preset
        self.world_seed = world_seed
        self.artifacts_root = artifacts_root
        # Кэш для хранения ключевых данных регионов (используется для анализа швов)
        self.processed_region_cache: Dict[Tuple[int, int], Dict[str, np.ndarray]] = {}

    def process(self, scx: int, scz: int, chunks_with_border: Dict[Tuple[int, int], GenResult]) -> Dict[
        Tuple[int, int], GenResult]:
        """
        Основной метод, запускающий полный цикл обработки региона.
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
        # ======================================================================
        # --- КОНЕЦ БЛОКА 0 ---
        # ======================================================================

        # ======================================================================
        # --- БЛОК 1: ГЕНЕРАЦИЯ РЕЛЬЕФА (ELEVATION) ---
        # ======================================================================
        stitched_height_ext = generate_elevation_region(
            self.world_seed, scx, scz, preset_region_size, chunk_size, self.preset, scratch_buffers
        )
        # ======================================================================
        # --- КОНЕЦ БЛОКА 1 ---
        # ======================================================================

        # ======================================================================
        # --- БЛОК 2: ТЕКСТУРИРОВАНИЕ И ГИДРОЛОГИЯ ---
        # ======================================================================
        stitched_surface_ext = np.empty((ext_size, ext_size), dtype=const.SURFACE_DTYPE)
        stitched_nav_ext = np.empty((ext_size, ext_size), dtype=const.NAV_DTYPE)

        # 1. "Грунтовка": вся суша покрывается землей и делается проходимой.
        classify_initial_terrain(stitched_surface_ext, stitched_nav_ext)

        # 2. СНАЧАЛА создаем высокогорные озера.
        generate_highland_lakes(
            stitched_height_ext, stitched_surface_ext, stitched_nav_ext,
            None, self.preset, self.world_seed
        )

        # 3. ПОТОМ применяем уровень моря.
        apply_sea_level(stitched_height_ext, stitched_surface_ext, stitched_nav_ext, self.preset)

        # 4. Наносим песок на пляжи.
        apply_beach_sand(stitched_height_ext, stitched_surface_ext, self.preset)

        # 5. Покрываем крутые склоны текстурой скал.
        apply_slope_textures(stitched_height_ext, stitched_surface_ext, self.preset)

        # 6. Генерируем реки.
        river_mask_ext = generate_rivers(
            stitched_height_ext, stitched_surface_ext, stitched_nav_ext, self.preset, chunk_size
        )
        # ======================================================================
        # --- КОНЕЦ БЛОКА 2 ---
        # ======================================================================

        # ======================================================================
        # --- БЛОК 3: ГЕНЕРАЦИЯ КЛИМАТА ---
        # ======================================================================
        stitched_layers_ext = {
            'height': stitched_height_ext,
            'surface': stitched_surface_ext,
            'navigation': stitched_nav_ext,
            'river': river_mask_ext
        }

        climate_maps = generate_climate_maps(
            stitched_layers_ext, self.preset, self.world_seed,
            scx, scz, ext_size, scratch_buffers=scratch_buffers
        )
        stitched_layers_ext.update(climate_maps)
        # ======================================================================
        # --- КОНЕЦ БЛОКА 3 ---
        # ======================================================================

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
                          if k in ['temperature', 'humidity', 'shadow', 'coast', 'river', 'temp_dry']}
        if layers_to_save:
            write_raw_regional_layers(str(region_raw_path / "climate_layers.npz"), layers_to_save, verbose=True)

        base_cx, base_cz = region_base(scx, scz, preset_region_size)
        final_chunks = {
            k: v for k, v in chunks_with_border.items()
            if base_cx <= k[0] < base_cx + preset_region_size and base_cz <= k[1] < base_cz + preset_region_size
        }

        _apply_changes_to_chunks(analysis.layers_core, final_chunks, base_cx, base_cz, chunk_size)
        # ======================================================================
        # --- КОНЕЦ БЛОКА 4 ---
        # ======================================================================

        print(
            f"[RegionProcessor] < Конвейер для региона ({scx}, {scz}) завершен. Время: {(time.perf_counter() - t_start) * 1000:.2f} мс")
        return final_chunks