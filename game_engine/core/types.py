# engine/worldgen_core/base/types.py
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List, Protocol


@dataclass
class GenResult:
    """Структура данных для хранения результата генерации чанка."""

    version: str
    type: str
    seed: int
    cx: int
    cz: int
    size: int
    cell_size: float
    layers: Dict[str, Any] = field(default_factory=dict)
    fields: Dict[str, Any] = field(default_factory=dict)
    ports: Dict[str, List[int]] = field(
        default_factory=lambda: {"N": [], "E": [], "S": [], "W": []}
    )
    blocked: bool = False
    metrics: Dict[str, Any] = field(default_factory=dict)
    stage_seeds: Dict[str, int] = field(default_factory=dict)
    capabilities: Dict[str, Any] = field(
        default_factory=lambda: {"has_roads": False, "has_biomes": False}
    )

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
    """Интерфейс, который должен реализовывать любой генератор."""

    def generate(self, params: Dict[str, Any]) -> GenResult: ...
    def capabilities(self) -> Dict[str, Any]: ...
