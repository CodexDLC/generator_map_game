from __future__ import annotations
import math
import time
from typing import Any, Dict

from .types import IGenerator, GenResult
from .utils import init_rng, make_empty_layers
from .validate import compute_metrics
from ..grid_alg.terrain import generate_elevation, classify_terrain, apply_slope_obstacles
from ..base.constants import KIND_ROAD
from ..base.start_gate import apply_start_gate_shapes, paint_start_gate_road


class BaseGenerator(IGenerator):
    """
    Базовый генератор чанка:
      1) генерирует высоты (бесшовно по миру);
      2) опционально формирует «площадку хаба» (центр чанка);
      3) классифицирует тайлы (water/ground/obstacle);
      4) помечает «склоны» (slope) по перепаду высот.
    НИКАКИХ дорог, портов и сетей в этой базовой версии нет.
    """

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

        # --- 1) Высоты ---
        t = time.perf_counter()
        elevation_grid = generate_elevation(stage_seeds["elevation"], cx, cz, size, self.preset)
        timings["elevation"] = (time.perf_counter() - t) * 1000.0

        # --- 1.1) Хаб-площадка (если включена в пресете) ---
        t = time.perf_counter()
        # Стартовая площадка/стена (вынесено в модуль)
        start_gate_info = apply_start_gate_shapes(elevation_grid, self.preset, cx, cz)
        if cx == 1 and cz == 0:
            print("[DBG] start_gate_info =", start_gate_info)
            print("[DBG] preset.start_gate =", getattr(self.preset, "start_gate", None))

        if start_gate_info and "stats" in start_gate_info:
            # чтобы видеть эффект в дампе метрик (даже если твой принтер их не выводит)
            layers_stats = start_gate_info["stats"]
        else:
            layers_stats = {"pad_cells": 0, "wall_cells": 0}
        timings["start_gate_shapes"] = (time.perf_counter() - t) * 1000.0

        # --- 2) Классификация + склоны ---
        t = time.perf_counter()
        classify_terrain(elevation_grid, layers["kind"], self.preset)
        apply_slope_obstacles(elevation_grid, layers["kind"], self.preset)
        timings["classify+slope"] = (time.perf_counter() - t) * 1000.0

        # --- 2.1) Дорожная вставка на площадке (если это базовый чанк) ---
        t = time.perf_counter()
        paint_start_gate_road(layers["kind"], start_gate_info)
        timings["start_gate_paint"] = (time.perf_counter() - t) * 1000.0

        # --- 3) Слои/метрики ---
        layers["height_q"]["grid"] = elevation_grid
        total_ms = (time.perf_counter() - t0) * 1000.0
        timings["total_ms"] = total_ms

        # BACK-COMPAT для твоего принтера: ключ 'connectivity' должен существовать
        timings.setdefault("connectivity", 0.0)

        result = GenResult(
            version=self.VERSION, type=self.TYPE,
            seed=seed, cx=cx, cz=cz, size=size, cell_size=1.0,
            layers=layers, stage_seeds=stage_seeds
        )
        result.metrics["gen_timings_ms"] = timings

        metrics_cover: Dict[str, Any] = compute_metrics(layers["kind"])
        result.metrics["start_gate"] = (start_gate_info.get("stats") if start_gate_info else {"pad_cells":0,"wall_cells":0})
        dist = float(math.hypot(cx, cz))
        metrics_cover["difficulty"] = {"value": dist / 10.0, "dist": dist}
        result.metrics = {**metrics_cover, **result.metrics}
        return result

