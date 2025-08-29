# engine/worldgen_core/world/world_base.py

from __future__ import annotations
from typing import Any, Dict, List, Tuple
from ..base.generator import BaseGenerator
from ..base.rng import split_chunk_seed
from .ops import (
    apply_border_ring, carve_port_window, inner_point_for_side,
    choose_ports,
    compute_hint_and_halo, edges_tiles_and_pass_from_kind, find_path_network, dijkstra_path, carve_path_emergency,
)
from ..grid_alg.terrain import generate_elevation, classify_terrain

BORDER_THICKNESS_DEFAULT = 2
HALO_THICKNESS_DEFAULT = 2
OPENING_WIDTH = 3
PATH_WIDTH = 3


class WorldBaseGenerator(BaseGenerator):
    """
    Оркестратор генерации мира на основе карты высот.
    1. Генерирует базовый рельеф (elevation).
    2. Классифицирует ландшафт (вода, земля, скалы) по высоте.
    3. Добавляет рамку, порты и соединяет их естественными путями.
    """

    def _init_rng(self, seed: int, cx: int, cz: int) -> Dict[str, int]:
        """
        Инициализирует ключи для всех этапов генерации.
        Мы возвращаем 'obstacles' и 'water' для совместимости
        со старой функцией compute_hint_and_halo.
        """
        base = split_chunk_seed(seed, cx, cz)
        return {
            "elevation": base ^ 0x01,
            "obstacles": base ^ 0x02, # <-- Возвращаем для hint/halo
            "water":     base ^ 0x03, # <-- Возвращаем для hint/halo
            "ports":     base ^ 0x04,
            "fields":    base ^ 0x05,
        }


    def _generate_world_layers(self, stage_seeds: Dict[str, int], layers: Dict[str, Any],
                               params: Dict[str, Any]) -> None:
        """Основной метод, заменяющий _scatter_obstacles_and_water и _assign_heights."""
        size = len(layers["kind"])
        cx = int(params.get("cx", 0))
        cz = int(params.get("cz", 0))
        preset = getattr(self, "preset", None)

        # 1. Генерируем карту высот (elevation)
        elevation_grid = generate_elevation(stage_seeds["elevation"], cx, cz, size)

        # Сохраняем высоты в слои. Формат [0, 1] удобен для клиента.
        # Клиент может умножить это значение на свою константу высоты.
        layers["height_q"]["grid"] = elevation_grid
        layers["height_q"]["scale"] = 1.0  # Теперь scale не нужен, высоты уже нормализованы
        layers["height_q"]["zero"] = 0.0

        # 2. Классифицируем ландшафт по высотам
        classify_terrain(elevation_grid, layers["kind"], preset)

        # 3. Рамка-барьер
        self._border_t = int(getattr(preset, "border_thickness", BORDER_THICKNESS_DEFAULT))
        apply_border_ring(layers["kind"], self._border_t)

        # 4. Hint/Halo (оставим для совместимости, но можно будет улучшить)
        self._halo_t = HALO_THICKNESS_DEFAULT
        obs_cfg = getattr(preset, "obstacles", {}) if preset else {}
        wat_cfg = getattr(preset, "water", {}) if preset else {}
        self._edges_hint, self._edges_halo = compute_hint_and_halo(
            stage_seeds, cx, cz, size, obs_cfg, wat_cfg, self._halo_t
        )

    # Переопределяем пайплайн из BaseGenerator
    def _scatter_obstacles_and_water(self, stage_seeds: Dict[str, int], layers: Dict[str, Any],
                                     params: Dict[str, Any]) -> None:
        # Этот метод теперь вызывает наш новый основной метод
        self._generate_world_layers(stage_seeds, layers, params)

    def _assign_heights_for_impassables(self, stage_seeds: Dict[str, int], layers: Dict[str, Any],
                                        params: Dict[str, Any]) -> None:
        # Этот метод больше не нужен, так как высоты генерируются для всей карты в _generate_world_layers.
        # Оставляем его пустым, чтобы не нарушать контракт с BaseGenerator.
        pass

    def _place_ports(self, stage_seeds: Dict[str, int], layers: Dict[str, Any], params: Dict[str, Any]) -> Dict[
        str, List[int]]:
        size = len(layers["kind"])
        seed = int(params.get("seed", 0))
        cx = int(params.get("cx", 0))
        cz = int(params.get("cz", 0))
        kind = layers["kind"]
        height_grid = layers["height_q"]["grid"]

        ports_cfg = getattr(self.preset, "ports", {"min": 2, "max": 4, "edge_margin": 3})
        ports = choose_ports(seed, cx, cz, size, ports_cfg)

        inner_points: List[Tuple[int, int]] = []
        for side, arr in ports.items():
            if not arr: continue
            idx = arr[0]
            carve_port_window(kind, side, idx, self._border_t, OPENING_WIDTH)
            inner_points.append(inner_point_for_side(side, idx, size, self._border_t))

        if len(inner_points) >= 2:
            # Находим сеть путей, но НЕ меняем kind_grid
            path_network = find_path_network(kind, height_grid, inner_points)
            layers["roads"] = path_network

            # <<< НОВЫЙ ШАГ: ГАРАНТИЯ СВЯЗНОСТИ >>>
            self._ensure_connectivity(layers, inner_points)

            self._ports_for_meta = ports
        return ports

    def _ensure_connectivity(self, layers: Dict[str, Any], points: List[Tuple[int, int]]):
        """Проверяет связность и пробивает туннели, если нужно."""
        if len(points) < 2:
            return

        kind = layers["kind"]
        height_grid = layers["height_q"]["grid"]

        # Правило: если всего 2 выхода, они должны быть связаны железно.
        if len(points) == 2:
            start, end = points[0], points[1]
            path = dijkstra_path(kind, height_grid, start, end)

            if path is None:

                emergency_path = []
                x1, z1 = start
                x2, z2 = end
                dx, dz = x2 - x1, z2 - z1
                steps = max(abs(dx), abs(dz))
                for i in range(steps + 1):
                    t = i / steps
                    x = round(x1 + t * dx)
                    z = round(z1 + t * dz)
                    emergency_path.append((x, z))

                carve_path_emergency(kind, emergency_path)

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

