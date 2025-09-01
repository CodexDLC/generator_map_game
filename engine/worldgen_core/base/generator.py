# engine/worldgen_core/base/generator.py
from __future__ import annotations
import math
import time
from typing import Any, Dict

from .types import IGenerator, GenResult
from .utils import init_rng, make_empty_layers
from .validate import compute_metrics
from ..grid_alg.terrain import generate_elevation, classify_terrain, apply_slope_obstacles


# --- УБИРАЕМ ВСЕ ИМПОРТЫ, СВЯЗАННЫЕ С START_GATE ---

class BaseGenerator(IGenerator):
    """
    Базовый генератор чанка:
      1) генерирует высоты (бесшовно по миру);
      2) классифицирует тайлы (water/ground/obstacle);
      3) помечает «склоны» (slope) по перепаду высот.
    НИКАКИХ дорог, площадок и прочих сценарных объектов здесь нет.
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

        # --- <<< ВЕСЬ БЛОК С ЛОГИКОЙ START_GATE ПОЛНОСТЬЮ УДАЛЕН ОТСЮДА >>> ---

        # --- 2) Классификация + склоны ---
        t = time.perf_counter()
        classify_terrain(elevation_grid, layers["kind"], self.preset)
        apply_slope_obstacles(elevation_grid, layers["kind"], self.preset)
        timings["classify+slope"] = (time.perf_counter() - t) * 1000.0

        # --- <<< БЛОК С РИСОВАНИЕМ ДОРОГИ НА ПЛОЩАДКЕ УДАЛЕН >>> ---

        # --- 3) Слои/метрики ---
        layers["height_q"]["grid"] = elevation_grid
        total_ms = (time.perf_counter() - t0) * 1000.0
        timings["total_ms"] = total_ms

        timings.setdefault("connectivity", 0.0)

        result = GenResult(
            version=self.VERSION, type=self.TYPE,
            seed=seed, cx=cx, cz=cz, size=size, cell_size=1.0,
            layers=layers, stage_seeds=stage_seeds
        )
        result.metrics["gen_timings_ms"] = timings

        metrics_cover: Dict[str, Any] = compute_metrics(layers["kind"])
        # --- <<< УДАЛЕНА МЕТРИКА ДЛЯ START_GATE >>> ---
        dist = float(math.hypot(cx, cz))
        metrics_cover["difficulty"] = {"value": dist / 10.0, "dist": dist}
        result.metrics = {**metrics_cover, **result.metrics}
        return result