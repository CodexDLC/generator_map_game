
from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, Mapping

KIND_GROUND = "ground"
KIND_OBSTACLE = "obstacle"
KIND_WATER = "water"
KIND_VOID = "void"
KIND_VALUES = (KIND_GROUND, KIND_OBSTACLE, KIND_WATER, KIND_VOID)

DEFAULT_PALETTE: Dict[str, str] = {
    KIND_GROUND: "#7a9e7a",
    KIND_OBSTACLE: "#444444",
    KIND_WATER: "#3573b8",
    KIND_VOID: "#00000000",
}

@dataclass(frozen=True)
class Preset:
    id: str = "world/base_default"
    size: int = 64
    cell_size: float = 1.0

    obstacles: Dict[str, Any] = field(default_factory=lambda: {"density": 0.12, "min_blob": 8, "max_blob": 64})
    water: Dict[str, Any] = field(default_factory=lambda: {"density": 0.05, "lake_chance": 0.2})
    height_q: Dict[str, Any] = field(default_factory=lambda: {"scale": 0.1})
    ports: Dict[str, Any] = field(default_factory=lambda: {"min": 2, "max": 4, "edge_margin": 3})
    fields: Dict[str, Any] = field(default_factory=lambda: {
        "temperature": {"enabled": True, "downsample": 4, "scale": 0.5},
        "humidity":    {"enabled": True, "downsample": 4, "scale": 0.5},
    })
    export: Dict[str, Any] = field(default_factory=lambda: {"palette": DEFAULT_PALETTE.copy(), "thick": True})

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @staticmethod
    def _deep_merge(base: Dict[str, Any], overrides: Mapping[str, Any]) -> Dict[str, Any]:
        out = dict(base)
        for k, v in overrides.items():
            if isinstance(v, Mapping) and isinstance(out.get(k), dict):
                out[k] = Preset._deep_merge(out[k], v)
            else:
                out[k] = v
        return out

    def merge_overrides(self, overrides: Mapping[str, Any]) -> "Preset":
        merged = self._deep_merge(self.to_dict(), overrides)
        return Preset.from_dict(merged)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Preset":
        default = cls().to_dict()
        merged = cls._deep_merge(default, dict(data))
        obj = cls(
            id=merged["id"], size=int(merged["size"]), cell_size=float(merged["cell_size"]),
            obstacles=dict(merged["obstacles"]), water=dict(merged["water"]),
            height_q=dict(merged["height_q"]), ports=dict(merged["ports"]),
            fields=dict(merged["fields"]), export=dict(merged["export"]),
        )
        obj.validate()
        return obj

    def validate(self) -> None:
        if not isinstance(self.id, str) or not self.id:
            raise ValueError("Preset.id must be non-empty string")
        if self.size < 8:
            raise ValueError("Preset.size must be >= 8")
        if self.cell_size <= 0:
            raise ValueError("Preset.cell_size must be > 0")

        od = float(self.obstacles.get("density", 0.0))
        if not (0.0 <= od <= 1.0):
            raise ValueError("obstacles.density must be in [0,1]")
        mn = int(self.obstacles.get("min_blob", 1))
        mx = int(self.obstacles.get("max_blob", mn))
        if not (1 <= mn <= mx):
            raise ValueError("obstacles.min_blob <= max_blob and >= 1")

        wd = float(self.water.get("density", 0.0))
        if not (0.0 <= wd <= 1.0):
            raise ValueError("water.density must be in [0,1]")
        lc = float(self.water.get("lake_chance", 0.0))
        if not (0.0 <= lc <= 1.0):
            raise ValueError("water.lake_chance must be in [0,1]")

        hs = float(self.height_q.get("scale", 0.1))
        if hs <= 0:
            raise ValueError("height_q.scale must be > 0")

        pmin = int(self.ports.get("min", 2))
        pmax = int(self.ports.get("max", 4))
        if not (1 <= pmin <= pmax <= 4):
            raise ValueError("ports.min/max must satisfy 1 <= min <= max <= 4")
        em = int(self.ports.get("edge_margin", 0))
        if not (0 <= em < self.size // 2):
            raise ValueError("ports.edge_margin must be >=0 and < size/2")

        for key in ("temperature", "humidity"):
            cfg = dict(self.fields.get(key, {}))
            if cfg.get("enabled"):
                ds = int(cfg.get("downsample", 4))
                if ds <= 0:
                    raise ValueError(f"fields.{key}.downsample must be > 0")
                sc = float(cfg.get("scale", 1.0))
                if sc <= 0:
                    raise ValueError(f"fields.{key}.scale must be > 0")

        pal = dict(self.export.get("palette", {}))
        for k in KIND_VALUES:
            if k not in pal:
                raise ValueError(f"export.palette must contain color for '{k}'")
            col = str(pal[k])
            if not col.startswith("#"):
                raise ValueError(f"export.palette['{k}'] must be hex like '#RRGGBB' or '#AARRGGBB'")

DEFAULT_BASE_PRESET = Preset()
