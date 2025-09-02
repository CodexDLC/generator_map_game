from __future__ import annotations
import math
import time
from typing import Any, Dict

from ...core.types import GenResult
from ...core.utils.rng import init_rng
from ...core.utils.layers import make_empty_layers
from ...core.utils.metrics import compute_metrics
from ...algorithms.terrain.terrain import generate_elevation, classify_terrain, apply_slope_obstacles
from .pregen_rules import early_fill_decision, modify_elevation_inplace # <- обновлено


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

        timings: Dict[str, float] = {}
        t0 = time.perf_counter()

        stage_seeds = init_rng(seed, cx, cz)
        layers = make_empty_layers(size)

        # --- Прережим ---
        pre_fill = early_fill_decision(cx, cz, size, self.preset, seed)
        if pre_fill:
            kind_name, height_value = pre_fill
            elevation_grid = [[float(height_value) for _ in range(size)] for _ in range(size)]
            layers["height_q"]["grid"] = elevation_grid
            for z in range(size):
                row = layers["kind"][z]
                for x in range(size):
                    row[x] = kind_name
            timings = {"elevation": 0.0, "classify+slope": 0.0}
            total_ms = (time.perf_counter() - t0) * 1000.0
            timings["total_ms"] = total_ms
            result = GenResult(
                version=self.VERSION, type=self.TYPE,
                seed=seed, cx=cx, cz=cz, size=size, cell_size=1.0,
                layers=layers, stage_seeds=stage_seeds
            )
            result.metrics["gen_timings_ms"] = timings
            metrics_cover: Dict[str, Any] = compute_metrics(layers["kind"])
            dist = float(math.hypot(cx, cz))
            metrics_cover["difficulty"] = {"value": dist / 10.0, "dist": dist}
            result.metrics = {**metrics_cover, **result.metrics}
            return result

        # 1) Высоты
        elevation_grid = generate_elevation(stage_seeds["elevation"], cx, cz, size, self.preset)

        # 2) Берега
        modify_elevation_inplace(elevation_grid, cx, cz, size, self.preset, seed)


        # 3) Классификация + склоны
        classify_terrain(elevation_grid, layers["kind"], self.preset)
        apply_slope_obstacles(elevation_grid, layers["kind"], self.preset)

        # 4) Слои/метрики
        layers["height_q"]["grid"] = elevation_grid
        timings["total_ms"] = (time.perf_counter() - t0) * 1000.0
        result = GenResult(
            version=self.VERSION, type=self.TYPE,
            seed=seed, cx=cx, cz=cz, size=size, cell_size=1.0,
            layers=layers, stage_seeds=stage_seeds
        )
        result.metrics["gen_timings_ms"] = timings
        metrics_cover: Dict[str, Any] = compute_metrics(layers["kind"])
        dist = float(math.hypot(cx, cz))
        metrics_cover["difficulty"] = {"value": dist / 10.0, "dist": dist}
        result.metrics = {**metrics_cover, **result.metrics}
        return result
