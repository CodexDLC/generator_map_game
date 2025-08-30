# engine/worldgen_core/world/world_generator.py
from __future__ import annotations
from typing import Any, Dict, List, Tuple

from ..base.generator import BaseGenerator, GenResult
from .ops import (
    apply_border_ring, carve_port_window, inner_point_for_side,
    choose_ports, find_path_network, dijkstra_path, carve_path_emergency,
    compute_hint_and_halo, edges_tiles_and_pass_from_kind
)


class WorldGenerator(BaseGenerator):
    """
    Декоратор, который берет базовый ландшафт и добавляет на него
    логику открытого мира: порты, дороги, связность.
    """

    def generate(self, params: Dict[str, Any]) -> GenResult:
        # 1. Получаем "сырой" ландшафт от родителя
        result = super().generate(params)

        # 2. Применяем "декорации" открытого мира
        self._add_border(result)
        ports = self._place_ports(result, params)
        result.ports = ports

        # 3. Добавляем метаданные для бесшовной стыковки
        self._add_edge_meta(result)

        return result

    def _add_border(self, result: GenResult):
        apply_border_ring(result.layers["kind"], 2)

    def _place_ports(self, result: GenResult, params: Dict[str, Any]) -> Dict[str, List[int]]:
        size = result.size
        seed = result.seed
        cx, cz = result.cx, result.cz
        kind = result.layers["kind"]
        height_grid = result.layers["height_q"]["grid"]

        ports_cfg = getattr(self.preset, "ports", {})
        ports = choose_ports(seed, cx, cz, size, ports_cfg, params, kind)

        inner_points = []
        for side, arr in ports.items():
            if arr:
                idx = arr[0]
                carve_port_window(kind, side, idx, 2, 3)
                inner_points.append(inner_point_for_side(side, idx, size, 2))

        if len(inner_points) >= 2:
            paths = find_path_network(kind, height_grid, inner_points)
            result.layers["roads"] = paths
            self._ensure_connectivity(kind, height_grid, inner_points, paths)

        return ports

    def _ensure_connectivity(self, kind, height_grid, points, paths):
        # Гарантируем связность для 2-х портов, если "честный" путь не нашелся
        if len(points) == 2 and paths and paths[0] is None:
            start, end = points[0], points[1]
            emergency_path = []  # Простая прямая линия как запасной вариант
            x1, z1 = start;
            x2, z2 = end
            steps = max(abs(x2 - x1), abs(z2 - z1))
            for i in range(steps + 1):
                t = i / steps
                x, z = round(x1 + t * (x2 - x1)), round(z1 + t * (z2 - z1))
                emergency_path.append((x, z))
            carve_path_emergency(kind, emergency_path)

    def _add_edge_meta(self, result: GenResult):
        # Эта логика осталась от старого генератора, пока просто переносим
        obs_cfg = getattr(self.preset, "obstacles", {})
        wat_cfg = getattr(self.preset, "water", {})
        hint, halo = compute_hint_and_halo(result.stage_seeds, result.cx, result.cz, result.size, obs_cfg, wat_cfg, 2)
        tiles_pass = edges_tiles_and_pass_from_kind(result.layers["kind"])
        result.metrics["edges"] = {
            "N": {**tiles_pass["N"], "hint": hint["N"], "halo": halo["N"]},
            "E": {**tiles_pass["E"], "hint": hint["E"], "halo": halo["E"]},
            "S": {**tiles_pass["S"], "hint": hint["S"], "halo": halo["S"]},
            "W": {**tiles_pass["W"], "hint": hint["W"], "halo": halo["W"]},
        }