# base.py
from __future__ import annotations
import dataclasses
import numpy as np
from typing import Any, Dict

class Node:
    type: str = "Node"
    default_params: Dict[str, Any] = {}

    def __init__(self, params: Dict[str, Any] | None = None):
        self.params = {**self.default_params, **(params or {})}

    def apply(self, ctx: "Context", inputs: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError

@dataclasses.dataclass(frozen=True)
class Context:
    world_seed: int
    region_id: tuple[int, int]
    region_rect: tuple[int, int, int]  # (x0_px, z0_px, size_px)
    meters_per_pixel: float

# — реестр —
REGISTRY: dict[str, type[Node]] = {}
def register(cls: type[Node]) -> type[Node]:
    REGISTRY[cls.__name__] = cls
    return cls
