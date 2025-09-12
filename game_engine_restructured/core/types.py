# game_engine/core/types.py
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List, Protocol

# Добавляем импорт HexGridSpec
from .grid.hex import HexGridSpec


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

    grid_spec: HexGridSpec | None = None
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

    # --- НОВОЕ ПОЛЕ ---
    # Здесь будут временно храниться данные для server_hex_map.json
    hex_map_data: Dict[str, Any] = field(default_factory=dict)

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
