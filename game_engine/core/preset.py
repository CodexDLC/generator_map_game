# Файл: game_engine/core/preset.py
from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, Mapping

from .constants import SURFACE_KINDS, DEFAULT_PALETTE


@dataclass(frozen=True)
class Preset:
    id: str = "world/base_default"
    size: int = 128
    cell_size: float = 1.0
    initial_load_radius: int = 1
    region_size: int = 5

    city_wall: Dict[str, Any] = field(default_factory=dict)

    elevation: Dict[str, Any] = field(default_factory=lambda: {
        "enabled": True,
        "max_height_m": 60.0,
        "sea_level_m": 20.0,
        "shaping_power": 1.5,
        "quantization_step_m": 1.0,
        "smoothing_passes": 1,
        "terraform": [] # <-- ДОБАВЛЕНО: Значение по умолчанию для терраформинга
    })

    slope_obstacles: Dict[str, Any] = field(default_factory=lambda: {
        "enabled": False,
        "delta_h_threshold_m": 3.0,
        "band_cells": 2,
        "use_diagonals": False,
        "ignore_water_edges": True,
    })

    scatter: Dict[str, Any] = field(default_factory=lambda: {
        "enabled": False,
        "groups": {"noise_scale_tiles": 64.0, "threshold": 0.5},
        "details": {"noise_scale_tiles": 8.0, "threshold": 0.6},
        "thinning": {"enabled": True, "min_distance": 2}
    })

    obstacles: Dict[str, Any] = field(default_factory=lambda: {"density": 0.12, "min_blob": 8, "max_blob": 64})
    water: Dict[str, Any] = field(default_factory=lambda: {"density": 0.05, "lake_chance": 0.2})
    height_q: Dict[str, Any] = field(default_factory=lambda: {"scale": 0.1})
    ports: Dict[str, Any] = field(default_factory=lambda: {"min": 2, "max": 4, "edge_margin": 3})
    fields: Dict[str, Any] = field(default_factory=lambda: {
        "temperature": {"enabled": True, "downsample": 4, "scale": 0.5},
        "humidity": {"enabled": True, "downsample": 4, "scale": 0.5},
    })
    export: Dict[str, Any] = field(default_factory=lambda: {"palette": DEFAULT_PALETTE.copy(), "thick": True})
    pre_rules: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @staticmethod
    def _deep_merge(base: Dict[str, Any], overrides: Mapping[str, Any]) -> Dict[str, Any]:
        out = dict(base)
        for k, v in overrides.items():
            if isinstance(v, Mapping) and isinstance(out.get(k), dict): out[k] = Preset._deep_merge(out[k], v)
            else: out[k] = v
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
            region_size=int(merged["region_size"]),
            initial_load_radius=int(merged["initial_load_radius"]),
            city_wall=dict(merged.get("city_wall", {})),
            elevation=dict(merged["elevation"]),
            slope_obstacles=dict(merged.get("slope_obstacles", {})),
            scatter=dict(merged.get("scatter", {})),
            obstacles=dict(merged["obstacles"]), water=dict(merged["water"]),
            height_q=dict(merged["height_q"]), ports=dict(merged["ports"]),
            fields=dict(merged["fields"]), export=dict(merged["export"]),
            pre_rules=dict(merged.get("pre_rules", {}))
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
                if ds <= 0: raise ValueError(f"fields.{key}.downsample must be > 0")
                sc = float(cfg.get("scale", 1.0))
                if sc <= 0: raise ValueError(f"fields.{key}.scale must be > 0")

        # --- ИЗМЕНЕНИЕ: Проверяем палитру по новому списку SURFACE_KINDS ---
        pal = dict(self.export.get("palette", {}))
        for k in SURFACE_KINDS:
            if k not in pal:
                # Мы не требуем наличия цвета для 'void', так как он не рисуется
                if k == "void": continue
                raise ValueError(f"export.palette must contain color for surface '{k}'")
            col = str(pal[k])
            if not col.startswith("#"):
                raise ValueError(f"export.palette['{k}'] must be hex like '#RRGGBB' or '#AARRGGBB'")

        # ... (остальные проверки без изменений) ...
        sc_cfg = dict(self.scatter)
        if sc_cfg.get("enabled", False):
            sc_dens = float(sc_cfg.get("density_threshold", 0.0))
            if not (0.0 <= sc_dens <= 1.0):
                raise ValueError("scatter.density_threshold must be in [0,1]")


DEFAULT_BASE_PRESET = Preset()