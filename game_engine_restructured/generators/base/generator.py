# Файл: game_engine/generators/base/generator.py
from __future__ import annotations
import math
import time
from typing import Any, Dict



from ...core.constants import KIND_SAND, NAV_OBSTACLE
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
from .pregen_rules import early_fill_decision, apply_ocean_coast_rules


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
        
                # --- НАЧАЛО ИЗМЕНЕНИЙ (Фаза 1.2) ---
        grid_spec = HexGridSpec(
            edge_m=0.63,
            meters_per_pixel=0.8,
            chunk_px=size
        )
        cols, rows = grid_spec.dims_for_chunk()
        print(f"[HEX] HEX grid dims: {cols}x{rows}")
        # --- КОНЕЦ ИЗМЕНЕНИЙ ---
        
        t0 = time.perf_counter()
        stage_seeds = init_rng(seed, cx, cz)

        layers = make_empty_layers(size)

        # Логика pre-fill остается, она может быть полезна для других правил в будущем
        pre_fill = early_fill_decision(cx, cz, size, self.preset, seed)
        if pre_fill:
            kind_name, height_value = pre_fill
            elevation_grid = [
                [float(height_value) for _ in range(size)] for _ in range(size)
            ]
            layers["height_q"]["grid"] = elevation_grid
            layers["surface"] = [[KIND_SAND for _ in range(size)] for _ in range(size)]
            layers["navigation"] = [
                [NAV_OBSTACLE for _ in range(size)] for _ in range(size)
            ]
            result = GenResult(
                version=self.VERSION,
                type=self.TYPE,
                seed=seed,
                cx=cx,
                cz=cz,
                size=size,
                cell_size=getattr(self.preset, "cell_size", 1.0),
                layers=layers,
            )
            return result

        # 1. Генерируем рельеф по новому алгоритму из ТЗ
        elevation_grid, elevation_grid_with_margin = generate_elevation(
            stage_seeds["elevation"], cx, cz, size, self.preset
        )
        layers["height_q"]["grid"] = elevation_grid

        result = GenResult(
            version=self.VERSION,
            type=self.TYPE,
            seed=seed,
            cx=cx,
            cz=cz,
            size=size,
            cell_size=1.0,
            layers=layers,
            stage_seeds=stage_seeds,
            grid_spec=grid_spec,  # <-- ДОБАВЬТЕ ЭТУ СТРОКУ
        )

        # 2. Базовая классификация поверхности (все - земля)
        classify_terrain(
            elevation_grid,
            result.layers["surface"],
            result.layers["navigation"],
            self.preset,
        )

        # Правила для океана/побережья отключены в пресете, но вызов можно оставить
        # на случай, если они понадобятся в будущем.
        apply_ocean_coast_rules(result, self.preset)

        # --- НАЧАЛО ИЗМЕНЕНИЙ: Исправляем вызов apply_slope_obstacles ---
        # 3. Применяем маску склонов, используя карту высот С БОРДЮРОМ
        # Убираем лишние аргументы cx и cz, они больше не нужны.
        apply_slope_obstacles(
            elevation_grid_with_margin, result.layers["surface"], self.preset
        )
        # --- КОНЕЦ ИЗМЕНЕНИЙ ---

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