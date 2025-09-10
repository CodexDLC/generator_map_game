# Файл: game_engine/generators/base/generator.py
from __future__ import annotations
import math
import time
from typing import Any, Dict

# --- ИЗМЕНЕНИЯ: Добавляем импорт для воды ---
from ...core import constants as const
from ...algorithms.climate.climate import generate_climate_maps, apply_biomes_to_surface
from ...algorithms.water.water_planner import generate_lakes, generate_rivers
# --- КОНЕЦ ИЗМЕНЕНИЙ ---

from ...core.grid.hex import HexGridSpec
from ...core.types import GenResult
from ...core.utils.rng import init_rng
from ...core.utils.layers import make_empty_layers
from ...core.utils.metrics import compute_metrics
from ...algorithms.terrain.terrain import (
    generate_elevation,
    classify_terrain,
    apply_slope_obstacles,
)



class BaseGenerator:
    VERSION = "chunk_v1"
    TYPE = "world_chunk_base"

    def __init__(self, preset: Any):
        self.preset = preset

    def generate(self, params: Dict[str, Any]) -> GenResult:
        seed = int(params.get("seed", 0))
        cx = int(params.get("cx", 0))
        cz = int(params.get("cz", 0))
        size = int(getattr(self.preset, "size", 128))

        grid_spec = HexGridSpec(
            edge_m=0.63,
            meters_per_pixel=0.8,
            chunk_px=size
        )
        print(f"[HEX] HEX grid dims: {grid_spec.dims_for_chunk()}")

        t0 = time.perf_counter()
        stage_seeds = init_rng(seed, cx, cz)
        layers = make_empty_layers(size)

        # 1. Генерируем рельеф
        elevation_grid, elevation_grid_with_margin = generate_elevation(
            stage_seeds["elevation"], cx, cz, size, self.preset
        )
        layers["height_q"]["grid"] = elevation_grid

        result = GenResult(
            version=self.VERSION, type=self.TYPE, seed=seed, cx=cx, cz=cz,
            size=size, cell_size=1.0, layers=layers,
            stage_seeds=stage_seeds, grid_spec=grid_spec,
        )

        # ===============================================
        # ===== ЭТАП 2: ГИДРОЛОГИЯ ======================
        # ===============================================
        generate_lakes(result, self.preset)
        generate_rivers(result, self.preset)
        # ===============================================

        # 3. Базовая классификация поверхности
        elevation_grid = result.layers["height_q"]["grid"] # Перечитываем карту высот
        classify_terrain(
            elevation_grid,
            result.layers["surface"],
            result.layers["navigation"],
            self.preset,
        )

        # 4. Климат и Биомы
        generate_climate_maps(result, self.preset)
        apply_biomes_to_surface(result)

        # 5. Применяем маску склонов (рисуем скалы)
        apply_slope_obstacles(
            elevation_grid_with_margin, result.layers["surface"], self.preset
        )

        # (Остальной код метрик без изменений)
        result.metrics["gen_timings_ms"] = {
            "total_ms": (time.perf_counter() - t0) * 1000.0
        }
        metrics_cover: Dict[str, Any] = compute_metrics(
            result.layers["surface"], result.layers["navigation"]
        )
        dist = float(math.hypot(cx, cz))
        metrics_cover["difficulty"] = {"value": dist / 10.0, "dist": dist}
        result.metrics = {**metrics_cover, **result.metrics}

        return result