from dataclasses import dataclass
from typing import Any, Dict, Optional

@dataclass(frozen=True)
class Preset:
    id: str
    version: int
    size: int
    cell_size: float
    initial_load_radius: int
    region_size: int
    city_wall: Dict[str, Any]
    elevation: Dict[str, Any]
    terraform: Dict[str, Any]
    climate: Dict[str, Any]
    surfaces: Dict[str, Any]
    slope_obstacles: Dict[str, Any]
    scatter: Dict[str, Any]
    obstacles: Dict[str, Any]
    water: Dict[str, Any]
    height_q: Dict[str, Any]
    ports: Dict[str, Any]
    fields: Dict[str, Any]
    export: Dict[str, Any]
    pre_rules: Dict[str, Any]

    # новые
    raw: Dict[str, Any]
    use_node_graph: bool = False
    node_graph: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
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
            "surfaces": dict(self.surfaces),
            "slope_obstacles": dict(self.slope_obstacles),
            "scatter": dict(self.scatter),
            "obstacles": dict(self.obstacles),
            "water": dict(self.water),
            "height_q": dict(self.height_q),
            "ports": dict(self.ports),
            "fields": dict(self.fields),
            "export": dict(self.export),
            "pre_rules": dict(self.pre_rules),
            "use_node_graph": bool(self.use_node_graph),
            "node_graph": dict(self.node_graph) if isinstance(self.node_graph, dict) else None,
        }
