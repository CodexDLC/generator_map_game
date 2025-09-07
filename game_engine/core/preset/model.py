# ========================
# file: game_engine/core/preset/model.py
# ========================
from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict


@dataclass(frozen=True)
class Preset:
    """Immutable in-memory representation of a world generation preset (v2).


    Note: values are already merged with defaults and migrated to v2 schema
    by the loader before constructing this dataclass.
    """

    # identity & versioning
    id: str
    version: int

    # world grid
    size: int
    cell_size: float
    initial_load_radius: int
    region_size: int

    # optional legacy slot
    city_wall: Dict[str, Any]

    # core systems (dicts by design for forward-compat)
    elevation: Dict[str, Any]
    terraform: Dict[str, Any]
    climate: Dict[str, Any]

    slope_obstacles: Dict[str, Any]
    scatter: Dict[str, Any]

    # legacy blocks kept for compatibility
    obstacles: Dict[str, Any]
    water: Dict[str, Any]
    height_q: Dict[str, Any]
    ports: Dict[str, Any]
    fields: Dict[str, Any]

    export: Dict[str, Any]
    pre_rules: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        # Lightweight manual conversion to avoid importing asdict here
        return {
            "id": self.id,
            "version": self.version,
            "size": self.size,
            "cell_size": self.cell_size,
            "initial_load_radius": self.initial_load_radius,
            "region_size": self.region_size,
            "city_wall": dict(self.city_wall),
            "elevation": dict(self.elevation),
            "terraform": dict(self.terraform),
            "climate": dict(self.climate),
            "slope_obstacles": dict(self.slope_obstacles),
            "scatter": dict(self.scatter),
            "obstacles": dict(self.obstacles),
            "water": dict(self.water),
            "height_q": dict(self.height_q),
            "ports": dict(self.ports),
            "fields": dict(self.fields),
            "export": dict(self.export),
            "pre_rules": dict(self.pre_rules),
        }
