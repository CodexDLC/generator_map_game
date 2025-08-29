from __future__ import annotations
from typing import Any, Dict, List, Tuple
from ..base.generator import BaseGenerator
from ..base.rng import split_chunk_seed
from ..grid_alg.features import (
    make_obstacles_world, make_water_world, merge_masks_into_kind,
    make_height_for_impassables,
)
from .ops import (
    apply_border_ring, carve_port_window, inner_point_for_side,
    choose_ports, carve_connectivity,
    compute_hint_and_halo, edges_tiles_and_pass_from_kind,
)

BORDER_THICKNESS_DEFAULT = 2
HALO_THICKNESS_DEFAULT   = 2
OPENING_WIDTH            = 3
PATH_WIDTH               = 3

class WorldBaseGenerator(BaseGenerator):
    """Тонкий оркестратор: шумы → рамка → порты → коридор → метаданные edges."""

    def _init_rng(self, seed: int, cx: int, cz: int) -> Dict[str, int]:
        base = split_chunk_seed(seed, cx, cz)
        return {
            "obstacles": base ^ 0x01,
            "water":     base ^ 0x02,
            "ports":     base ^ 0x03,  # не используется в этой версии, но оставим
            "height":    base ^ 0x04,
            "fields":    base ^ 0x05,
        }

    def _scatter_obstacles_and_water(self, stage_seeds: Dict[str, int], layers: Dict[str, Any], params: Dict[str, Any]) -> None:
        size = len(layers["kind"])
        cx = int(params.get("cx", 0)); cz = int(params.get("cz", 0))
        preset = getattr(self, "preset", None)
        obs_cfg = getattr(preset, "obstacles", {}) if preset else {}
        wat_cfg = getattr(preset, "water", {}) if preset else {}

        self._border_t = int(getattr(preset, "border_thickness", BORDER_THICKNESS_DEFAULT)) if hasattr(preset, "border_thickness") else BORDER_THICKNESS_DEFAULT
        self._halo_t   = HALO_THICKNESS_DEFAULT

        # 1) сырой мир
        obstacles = make_obstacles_world(stage_seeds["obstacles"], cx, cz, size, obs_cfg)
        water     = make_water_world(stage_seeds["water"],     cx, cz, size, wat_cfg)
        kind = layers["kind"]
        merge_masks_into_kind(kind, obstacles, water)

        # 2) hint/halo по миру
        self._edges_hint, self._edges_halo = compute_hint_and_halo(
            stage_seeds, cx, cz, size, obs_cfg, wat_cfg, self._halo_t
        )

        # 3) рамка-барьер
        apply_border_ring(kind, self._border_t)

    def _assign_heights_for_impassables(self, stage_seeds: Dict[str, int], layers: Dict[str, Any], params: Dict[str, Any]) -> None:
        scale = 0.1
        preset = getattr(self, "preset", None)
        if preset and isinstance(getattr(preset, "height_q", None), dict):
            scale = float(preset.height_q.get("scale", 0.1))
        cx = int(params.get("cx", 0)); cz = int(params.get("cz", 0))
        grid = make_height_for_impassables(stage_seeds["height"], cx, cz, layers["kind"], scale)
        layers["height_q"]["zero"] = 0.0
        layers["height_q"]["scale"] = scale
        layers["height_q"]["grid"] = grid

    def _place_ports(self, stage_seeds: Dict[str, int], layers: Dict[str, Any], params: Dict[str, Any]) -> Dict[str, List[int]]:
        size = len(layers["kind"])
        seed = int(params.get("seed", 0))
        cx = int(params.get("cx", 0)); cz = int(params.get("cz", 0))
        kind = layers["kind"]

        ports_cfg = getattr(self.preset, "ports", {"min": 2, "max": 4, "edge_margin": 3})
        ports = choose_ports(seed, cx, cz, size, ports_cfg)

        inner_points: List[Tuple[int, int]] = []
        for side, arr in ports.items():
            if not arr: continue
            idx = arr[0]
            carve_port_window(kind, side, idx, self._border_t, OPENING_WIDTH)
            inner_points.append(inner_point_for_side(side, idx, size, self._border_t))

        if len(inner_points) >= 2:
            carve_connectivity(kind, inner_points, PATH_WIDTH)

        self._ports_for_meta = ports
        return ports

    def _compute_metrics(self, layers: Dict[str, Any], ports: Dict[str, List[int]]) -> Dict[str, Any]:
        size = len(layers.get("kind", [])) or 0
        total = size * size if size else 0
        open_cells = sum(1 for z in range(size) for x in range(size) if layers["kind"][z][x] == "ground")
        obstacle_cells = sum(1 for z in range(size) for x in range(size) if layers["kind"][z][x] == "obstacle")
        water_cells = sum(1 for z in range(size) for x in range(size) if layers["kind"][z][x] == "water")

        tiles_pass = edges_tiles_and_pass_from_kind(layers["kind"])
        return {
            "open_pct": (open_cells / total) if total else 0.0,
            "obstacle_pct": (obstacle_cells / total) if total else 0.0,
            "water_pct": (water_cells / total) if total else 0.0,
            "edges": {
                "N": {**tiles_pass["N"], "hint": self._edges_hint["N"], "halo": self._edges_halo["N"], "len": size},
                "E": {**tiles_pass["E"], "hint": self._edges_hint["E"], "halo": self._edges_halo["E"], "len": size},
                "S": {**tiles_pass["S"], "hint": self._edges_hint["S"], "halo": self._edges_halo["S"], "len": size},
                "W": {**tiles_pass["W"], "hint": self._edges_hint["W"], "halo": self._edges_halo["W"], "len": size},
                "border_thickness": self._border_t,
                "halo_thickness": self._halo_t,
            },
            "ports": getattr(self, "_ports_for_meta", ports),
        }
