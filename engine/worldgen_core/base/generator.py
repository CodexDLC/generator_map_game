
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List, Protocol, Tuple
import time

KIND_GROUND = "ground"
KIND_OBSTACLE = "obstacle"
KIND_WATER = "water"
KIND_VOID = "void"
KIND_VALUES = (KIND_GROUND, KIND_OBSTACLE, KIND_WATER, KIND_VOID)


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
        size = int(params.get("size", getattr(self.preset, "size", 64)))
        cell_size = float(params.get("cell_size", getattr(self.preset, "cell_size", 1.0)))

        t0 = time.perf_counter()
        stage_seeds = self._init_rng(seed, cx, cz)
        layers = self._make_empty_layers(size)
        self._scatter_obstacles_and_water(stage_seeds, layers, params)
        self._assign_heights_for_impassables(stage_seeds, layers, params)
        ports = self._place_ports(stage_seeds, layers, params)

        blocked = False  # диагностику путей добавим на A8 при наличии топологии/масок
        fields: Dict[str, Any] = {}
        metrics = self._compute_metrics(layers, ports)
        metrics.setdefault("gen_ms", int((time.perf_counter() - t0) * 1000))

        return GenResult(
            version=self.VERSION, type=self.TYPE,
            seed=seed, cx=cx, cz=cz, size=size, cell_size=cell_size,
            layers=layers, fields=fields, ports=ports, blocked=blocked,
            metrics=metrics, stage_seeds=stage_seeds,
        )

    def capabilities(self) -> Dict[str, Any]:
        return {"has_roads": False, "has_biomes": False, "version": self.VERSION, "type": self.TYPE}

    # --------- hooks to override ---------
    def _init_rng(self, seed: int, cx: int, cz: int) -> Dict[str, int]:
        return {
            "obstacles": seed ^ 0xA1B2C3D4,
            "water":     seed ^ 0xB2C3D4E5,
            "ports":     seed ^ 0xC3D4E5F6,
            "height":    seed ^ 0xD4E5F607,
            "fields":    seed ^ 0xE5F60718,
        }

    def _make_empty_layers(self, size: int) -> Dict[str, Any]:
        kind = [[KIND_GROUND for _ in range(size)] for _ in range(size)]
        height_q = [[0 for _ in range(size)] for _ in range(size)]
        return {
            "kind": kind,
            "height_q": {"zero": 0.0, "scale": 0.1, "grid": height_q},
        }

    def _scatter_obstacles_and_water(self, stage_seeds: Dict[str, int], layers: Dict[str, Any], params: Dict[str, Any]) -> None:
        return None

    def _assign_heights_for_impassables(self, stage_seeds: Dict[str, int], layers: Dict[str, Any], params: Dict[str, Any]) -> None:
        return None

    def _place_ports(self, stage_seeds: Dict[str, int], layers: Dict[str, Any], params: Dict[str, Any]) -> Dict[str, List[int]]:
        return {"N": [], "E": [], "S": [], "W": []}

    def _compute_metrics(self, layers: Dict[str, Any], ports: Dict[str, List[int]]) -> Dict[str, Any]:
        size = len(layers.get("kind", [])) or 0
        total = size * size if size else 0
        return {"open_pct": 1.0 if total else 0.0, "obstacle_pct": 0.0, "water_pct": 0.0}
