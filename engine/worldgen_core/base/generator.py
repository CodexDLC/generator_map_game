
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Protocol
import time

from engine.worldgen_core.base.rng import split_chunk_seed
from engine.worldgen_core.grid_alg.terrain import classify_terrain, generate_elevation

from engine.worldgen_core.base.constants import KIND_GROUND, KIND_OBSTACLE, KIND_WATER

@dataclass
class GenResult:
    version: str
    type: str
    seed: int
    cx: int
    cz: int
    size: int
    cell_size: float

    layers: Dict[str, Any] = field(default_factory=dict)
    fields: Dict[str, Any] = field(default_factory=dict)
    ports: Dict[str, List[int]] = field(default_factory=lambda: {"N": [], "E": [], "S": [], "W": []})
    blocked: bool = False

    metrics: Dict[str, Any] = field(default_factory=dict)
    stage_seeds: Dict[str, int] = field(default_factory=dict)
    capabilities: Dict[str, Any] = field(default_factory=lambda: {"has_roads": False, "has_biomes": False})

    def header(self) -> Dict[str, Any]:
        return {
            "version": self.version,
            "type": self.type,
            "seed": self.seed,
            "cx": self.cx,
            "cz": self.cz,
            "size": self.size,
            "cell_size": self.cell_size,
        }

    def meta_header(self) -> Dict[str, Any]:
        return self.header().copy()


class IGenerator(Protocol):
    def generate(self, params: Dict[str, Any]) -> GenResult: ...
    def capabilities(self) -> Dict[str, Any]: ...


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
        stage_seeds = self._init_rng(seed, cx, cz)
        layers = self._make_empty_layers(size)

        # --- Основная генерация ландшафта ---
        elevation_grid = generate_elevation(stage_seeds["elevation"], cx, cz, size)
        classify_terrain(elevation_grid, layers["kind"], self.preset)
        layers["height_q"]["grid"] = elevation_grid

        # --- Расчет метрик и сложности ---
        metrics = self._compute_base_metrics(layers)
        distance = math.sqrt(cx ** 2 + cz ** 2)
        metrics["difficulty"] = {"value": distance / 10.0, "dist": distance}
        metrics["gen_ms"] = int((time.perf_counter() - t0) * 1000)

        return GenResult(
            version=self.VERSION, type=self.TYPE,
            seed=seed, cx=cx, cz=cz, size=size, cell_size=1.0,
            layers=layers, metrics=metrics, stage_seeds=stage_seeds
        )

    def _init_rng(self, seed: int, cx: int, cz: int) -> Dict[str, int]:
        base = split_chunk_seed(seed, cx, cz)
        return {"elevation": base ^ 0x01}

    def _make_empty_layers(self, size: int) -> Dict[str, Any]:
        return {
            "kind": [[KIND_GROUND for _ in range(size)] for _ in range(size)],
            "height_q": {"grid": []}
        }

    def _compute_base_metrics(self, layers: Dict[str, Any]) -> Dict[str, Any]:
        size = len(layers.get("kind", []))
        if not size: return {}
        total = size * size
        counts = {"ground": 0, "obstacle": 0, "water": 0}
        for row in layers["kind"]:
            for tile in row:
                if tile in counts: counts[tile] += 1
        return {
            "open_pct": counts["ground"] / total,
            "obstacle_pct": counts["obstacle"] / total,
            "water_pct": counts["water"] / total,
        }
