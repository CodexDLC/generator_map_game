# Файл: game_engine_restructured/world/processing/base_processor.py
from __future__ import annotations
import time
from typing import Any, Dict

from ...core.grid.hex import HexGridSpec
from ...core.types import GenResult
from ...core.utils.rng import init_rng
from ...core.utils.layers import make_empty_layers
# --- НАЧАЛО ИЗМЕНЕНИЙ: Добавляем недостающий импорт ---
from ...algorithms.terrain.terrain import generate_elevation, classify_terrain
# --- КОНЕЦ ИЗМЕНЕНИЙ ---


class BaseProcessor:
    VERSION = "chunk_v1"
    TYPE = "world_chunk_base"

    def __init__(self, preset: Any):
        self.preset = preset

    def process(self, params: Dict[str, Any]) -> GenResult:
        seed = int(params.get("seed", 0))
        cx = int(params.get("cx", 0))
        cz = int(params.get("cz", 0))
        size = int(getattr(self.preset, "size", 128))

        grid_spec = HexGridSpec(
            edge_m=0.63,
            meters_per_pixel=float(self.preset.cell_size),
            chunk_px=size
        )
        t0 = time.perf_counter()
        stage_seeds = init_rng(seed, cx, cz)
        layers = make_empty_layers(size)

        # 1. Генерируем только рельеф
        elevation_grid, elevation_grid_with_margin = generate_elevation(
            stage_seeds["elevation"], cx, cz, size, self.preset
        )
        layers["height_q"]["grid"] = elevation_grid

        result = GenResult(
            version=self.VERSION, type=self.TYPE, seed=seed, cx=cx, cz=cz,
            size=size, cell_size=float(self.preset.cell_size), layers=layers,
            stage_seeds=stage_seeds, grid_spec=grid_spec,
        )

        # 2. Базовая классификация поверхности
        classify_terrain(
            elevation_grid,
            result.layers["surface"],
            result.layers["navigation"],
            self.preset,
        )

        result.metrics["gen_timings_ms"] = {
            "base_ms": (time.perf_counter() - t0) * 1000.0
        }

        # Сохраняем elevation_grid_with_margin для будущих этапов
        result.temp_data = {"elevation_with_margin": elevation_grid_with_margin}

        return result