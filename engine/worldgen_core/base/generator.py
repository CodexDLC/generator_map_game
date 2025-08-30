# engine/worldgen_core/base/generator.py
from __future__ import annotations
import math
import time

from typing import Any, Dict, List

from .types import IGenerator, GenResult
# --- Импорты ---
from .utils import init_rng, make_empty_layers
from .validate import compute_metrics
from ..grid_alg.terrain import classify_terrain, generate_elevation
from ..grid_alg.topology.metrics import compute_hint_and_halo, edges_tiles_and_pass_from_kind
# <<< ИЗМЕНЕНО: inner_point_for_side больше не нужен для рамки >>>
from ..grid_alg.topology.border import inner_point_for_side
from ..grid_alg.topology.connectivity import choose_ports
from ..grid_alg.topology.pathfinding import find_path_network, ensure_connectivity, apply_paths_to_grid


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
        elevation_grid = generate_elevation(stage_seeds["elevation"], cx, cz, size, self.preset)
        classify_terrain(elevation_grid, layers["kind"], self.preset)
        layers["height_q"]["grid"] = elevation_grid

        # --- Создаем объект результата ПОСЛЕ генерации ландшафта ---
        result = GenResult(
            version=self.VERSION, type=self.TYPE,
            seed=seed, cx=cx, cz=cz, size=size, cell_size=1.0,
            layers=layers, stage_seeds=stage_seeds
        )

        # --- ЭТАП 2: Создание структуры для связного мира ---
        # <<< УДАЛЕНО: apply_border_ring(result.layers["kind"], 2) >>>
        ports = self._place_ports(result, params)
        result.ports = ports
        self._add_edge_meta(result)

        # --- ЭТАП 3: Финальный расчет метрик ---
        metrics: Dict[str, Any] = compute_metrics(layers["kind"])
        distance = math.sqrt(cx ** 2 + cz ** 2)
        metrics["difficulty"] = {"value": distance / 10.0, "dist": distance}
        metrics["gen_ms"] = int((time.perf_counter() - t0) * 1000)
        result.metrics = {**metrics, **result.metrics}

        return result

    # --- Методы ---

    def _place_ports(self, result: GenResult, params: Dict[str, Any]) -> Dict[str, List[int]]:
        size = result.size
        kind = result.layers["kind"]
        height_grid = result.layers["height_q"]["grid"]

        ports_cfg = getattr(self.preset, "ports", {})
        obs_cfg = getattr(self.preset, "obstacles", {})
        wat_cfg = getattr(self.preset, "water", {})

        ports = choose_ports(result, ports_cfg, params, obs_cfg, wat_cfg)

        inner_points = []
        for side, arr in ports.items():
            if arr:
                idx = arr[0]
                # <<< УДАЛЕНО: carve_port_window(kind, side, idx, 2, 3) >>>
                # Точка для старта пути теперь прямо на границе чанка
                inner_points.append(inner_point_for_side(side, idx, size, 0))

        if len(inner_points) >= 2:
            paths = find_path_network(kind, height_grid, inner_points)
            ensure_connectivity(kind, height_grid, inner_points, paths)

            # <<< ВОТ РЕШЕНИЕ: Вызываем отрисовку дорог >>>
            apply_paths_to_grid(kind, paths)

            result.layers["roads"] = paths

        return ports

    def _add_edge_meta(self, result: GenResult):
        # (Этот метод без изменений)
        obs_cfg = getattr(self.preset, "obstacles", {})
        wat_cfg = getattr(self.preset, "water", {})
        hint, halo = compute_hint_and_halo(result.stage_seeds, result.cx, result.cz, result.size, obs_cfg, wat_cfg, 2)
        tiles_pass = edges_tiles_and_pass_from_kind(result.layers["kind"])
        result.metrics["edges"] = {
            "N": {**tiles_pass["N"], "hint": hint["N"], "halo": halo["N"]},
            "E": {**tiles_pass["E"], "hint": hint["E"], "halo": halo["E"]},
            "S": {**tiles_pass["S"], "hint": hint["S"], "halo": halo["S"]},
            "W": {**tiles_pass["W"], "hint": hint["W"], "halo": halo["W"]},
        }