# engine/worldgen_core/base/generator.py
from __future__ import annotations
import math
import time

from typing import Any, Dict, List

from .types import IGenerator, GenResult
# --- Импорты для всей базовой логики ---
from .utils import init_rng, make_empty_layers
from .validate import compute_metrics
from ..grid_alg.terrain import classify_terrain, generate_elevation
from ..grid_alg.topology.metrics import compute_hint_and_halo, edges_tiles_and_pass_from_kind
from ..grid_alg.topology.border import apply_border_ring, carve_port_window, inner_point_for_side
from ..grid_alg.topology.connectivity import choose_ports
from ..grid_alg.topology.pathfinding import find_path_network, ensure_connectivity




class BaseGenerator(IGenerator):
    VERSION = "chunk_v1"
    TYPE = "world_chunk_base"

    def __init__(self, preset: Any):
        self.preset = preset

    def generate(self, params: Dict[str, Any]) -> GenResult:
        seed = int(params.get("seed", 0))
        cx = int(params.get("cx", 0))
        cz = int(params.get("cz", 0))
        size = int(getattr(self.preset, "size", 128))
        t0 = time.perf_counter()

        # --- ЭТАП 1: Генерация "сырого" ландшафта ---
        stage_seeds = init_rng(seed, cx, cz)
        layers = make_empty_layers(size)
        elevation_grid = generate_elevation(stage_seeds["elevation"], cx, cz, size)
        classify_terrain(elevation_grid, layers["kind"], self.preset)
        layers["height_q"]["grid"] = elevation_grid

        # --- Создаем объект результата ПОСЛЕ генерации ландшафта ---
        result = GenResult(
            version=self.VERSION, type=self.TYPE,
            seed=seed, cx=cx, cz=cz, size=size, cell_size=1.0,
            layers=layers, stage_seeds=stage_seeds
        )

        # --- ЭТАП 2: Создание структуры для связного мира (бывшая логика WorldGenerator) ---
        apply_border_ring(result.layers["kind"], 2)
        ports = self._place_ports(result, params)
        result.ports = ports
        self._add_edge_meta(result) # Добавляем hint/halo

        # --- ЭТАП 3: Финальный расчет метрик ---
        metrics: Dict[str, Any] = compute_metrics(layers["kind"])
        distance = math.sqrt(cx ** 2 + cz ** 2)
        metrics["difficulty"] = {"value": distance / 10.0, "dist": distance}
        metrics["gen_ms"] = int((time.perf_counter() - t0) * 1000)
        # Добавляем к метрикам данные о границах, которые мы рассчитали
        result.metrics = {**metrics, **result.metrics}

        return result

    # --- Методы, перенесенные из WorldGenerator ---

    def _place_ports(self, result: GenResult, params: Dict[str, Any]) -> Dict[str, List[int]]:
        size = result.size; seed = result.seed; cx = result.cx; cz = result.cz
        kind = result.layers["kind"]
        height_grid = result.layers["height_q"]["grid"]
        ports_cfg = getattr(self.preset, "ports", {})

        ports = choose_ports(seed, cx, cz, size, ports_cfg, params, kind)

        inner_points = []
        for side, arr in ports.items():
            if arr:
                idx = arr[0]
                carve_port_window(kind, side, idx, 2, 3)
                inner_points.append(inner_point_for_side(side, idx, size, 2))

        if len(inner_points) >= 2:
            paths = find_path_network(kind, height_grid, inner_points)
            result.layers["roads"] = paths
            ensure_connectivity(kind, height_grid, inner_points, paths)

        return ports

    def _add_edge_meta(self, result: GenResult):
        obs_cfg = getattr(self.preset, "obstacles", {})
        wat_cfg = getattr(self.preset, "water", {})
        hint, halo = compute_hint_and_halo(result.stage_seeds, result.cx, result.cz, result.size, obs_cfg, wat_cfg, 2)
        tiles_pass = edges_tiles_and_pass_from_kind(result.layers["kind"])
        # Записываем данные о границах прямо в result.metrics, а не создаем новую переменную
        result.metrics["edges"] = {
            "N": {**tiles_pass["N"], "hint": hint["N"], "halo": halo["N"]},
            "E": {**tiles_pass["E"], "hint": hint["E"], "halo": halo["E"]},
            "S": {**tiles_pass["S"], "hint": hint["S"], "halo": halo["S"]},
            "W": {**tiles_pass["W"], "hint": hint["W"], "halo": halo["W"]},
        }