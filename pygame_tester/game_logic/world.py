# game_engine/game_logic/world.py
from typing import Dict, Any, Tuple, List
import math
import numpy as np

from game_engine_restructured.algorithms.pathfinding.a_star import find_path
from game_engine_restructured.core.constants import NAV_PASSABLE
from game_engine_restructured.core.grid.hex import HexGridSpec
from pygame_tester.config import PLAYER_MOVE_SPEED
from pygame_tester.game_logic.player import Player
from pygame_tester.world_manager import WorldManager


class GameWorld:
    def __init__(self, world_seed: int, grid_spec: HexGridSpec):
        self.world_manager = WorldManager(world_seed)
        self.grid_spec = grid_spec
        initial_q, initial_r = self.grid_spec.world_to_axial(0.0, 0.0)
        self.player = Player(q=initial_q, r=initial_r)
        self.render_grid_radius = 1
        self._loaded_chunks: Dict[Tuple[int, int], Dict] = {}
        self.last_player_chunk_pos = (-999, -999)
        self._update_surrounding_grid()

    def update(self, dt: float):
        player_cx, player_cz = self.grid_spec.axial_to_chunk_coords(
            self.player.q, self.player.r
        )
        if (player_cx, player_cz) != self.last_player_chunk_pos:
            self.last_player_chunk_pos = (player_cx, player_cz)
            print(
                f"[GameWorld] Player entered new chunk ({player_cx}, {player_cz}). Updating grid..."
            )
            self._update_surrounding_grid()

        self._handle_path_movement(dt)

    def _update_surrounding_grid(self):
        center_cx, center_cz = self.grid_spec.axial_to_chunk_coords(
            self.player.q, self.player.r
        )
        needed_chunks = set()
        for dz in range(-self.render_grid_radius, self.render_grid_radius + 1):
            for dx in range(-self.render_grid_radius, self.render_grid_radius + 1):
                needed_chunks.add((center_cx + dx, center_cz + dz))

        current_chunks = set(self._loaded_chunks.keys())
        for pos in current_chunks - needed_chunks:
            print(f"  -> Unloading chunk {pos}")
            del self._loaded_chunks[pos]

        for pos in needed_chunks - current_chunks:
            print(f"  -> Loading chunk {pos}")
            self._loaded_chunks[pos] = self.world_manager.get_chunk_data(pos[0], pos[1])

    def get_tile_at_axial(self, q: int, r: int) -> Dict:
        chunk_cx, chunk_cz = self.grid_spec.axial_to_chunk_coords(q, r)
        chunk_data = self._loaded_chunks.get((chunk_cx, chunk_cz))

        if not chunk_data:
            return {
                "surface": "void",
                "navigation": NAV_PASSABLE,
                "overlay": 0,
                "height": 0,
            }

        local_x, local_z = self.grid_spec.axial_to_local_px(q, r)

        # Безопасно получаем данные, возвращая None если слоя нет
        surface_grid = chunk_data.get("surface")
        nav_grid = chunk_data.get("navigation")
        overlay_grid = chunk_data.get("overlay")
        height_grid = chunk_data.get("height")

        # Проверка что все слои на месте и координаты корректны
        if not all([surface_grid, nav_grid]) or not (
            0 <= local_z < len(surface_grid) and 0 <= local_x < len(surface_grid[0])
        ):
            return {
                "surface": "void",
                "navigation": NAV_PASSABLE,
                "overlay": 0,
                "height": 0,
            }

        return {
            "surface": surface_grid[local_z][local_x],
            "navigation": nav_grid[local_z][local_x],
            "overlay": overlay_grid[local_z][local_x] if overlay_grid else 0,
            "height": height_grid[local_z][local_x] if height_grid else 0,
        }

    def _get_stitched_grids_for_pathfinding(
        self,
    ) -> Tuple[Dict[str, np.ndarray], Tuple[int, int]]:
        """Склеивает все загруженные чанки в одну большую карту для A*."""
        if not self._loaded_chunks:
            return {}, (0, 0)

        min_cx = min(c[0] for c in self._loaded_chunks.keys())
        min_cz = min(c[1] for c in self._loaded_chunks.keys())
        max_cx = max(c[0] for c in self._loaded_chunks.keys())
        max_cz = max(c[1] for c in self._loaded_chunks.keys())

        cols = max_cx - min_cx + 1
        rows = max_cz - min_cz + 1
        chunk_size = self.grid_spec.chunk_px

        stitched_surface = np.full(
            (rows * chunk_size, cols * chunk_size), "void", dtype=object
        )
        stitched_nav = np.full(
            (rows * chunk_size, cols * chunk_size), NAV_PASSABLE, dtype=object
        )
        stitched_height = np.zeros(
            (rows * chunk_size, cols * chunk_size), dtype=np.float32
        )

        for (cx, cz), chunk_data in self._loaded_chunks.items():
            if not chunk_data:
                continue

            x_offset = (cx - min_cx) * chunk_size
            z_offset = (cz - min_cz) * chunk_size

            if chunk_data.get("surface"):
                stitched_surface[
                    z_offset : z_offset + chunk_size, x_offset : x_offset + chunk_size
                ] = chunk_data["surface"]
            if chunk_data.get("navigation"):
                stitched_nav[
                    z_offset : z_offset + chunk_size, x_offset : x_offset + chunk_size
                ] = chunk_data["navigation"]
            if chunk_data.get("height"):
                stitched_height[
                    z_offset : z_offset + chunk_size, x_offset : x_offset + chunk_size
                ] = chunk_data["height"]

        stitched_grids = {
            "surface": stitched_surface.tolist(),
            "navigation": stitched_nav.tolist(),
            "height": stitched_height.tolist(),
        }

        # Смещение в гексах
        offset_q, offset_r = self.grid_spec.world_to_axial(
            min_cx * self.grid_spec.chunk_size_m, min_cz * self.grid_spec.chunk_size_m
        )

        return stitched_grids, (offset_q, offset_r)

    def set_player_target(self, target_wx: float, target_wz: float):
        print("\n[Pathfinder] Planning route...")
        stitched_grids, (offset_q, offset_r) = (
            self._get_stitched_grids_for_pathfinding()
        )

        if not stitched_grids:
            print("[Pathfinder] -> ERROR: No chunks loaded to plan a path.")
            return

        start_q, start_r = self.player.q, self.player.r
        goal_q, goal_r = self.grid_spec.world_to_axial(target_wx, target_wz)

        # Конвертируем глобальные hex-координаты в локальные для склеенной карты
        local_start = (start_q - offset_q, start_r - offset_r)
        local_goal = (goal_q - offset_q, goal_r - offset_r)

        print(
            f"[Pathfinder] -> Global Start: ({start_q},{start_r}), Goal: ({goal_q},{goal_r})"
        )
        print(
            f"[Pathfinder] -> Local Start: {local_start}, Goal: {local_goal} with offset ({offset_q}, {offset_r})"
        )

        path = find_path(
            stitched_grids["surface"],
            stitched_grids["navigation"],
            stitched_grids.get("height"),
            local_start,
            local_goal,
        )

        if path:
            # Конвертируем локальный путь обратно в глобальные координаты
            self.player.path = [(q + offset_q, r + offset_r) for q, r in path]
            print(
                f"[Pathfinder] -> SUCCESS: Path found with {len(self.player.path)} waypoints."
            )
        else:
            self.player.path = []
            print("[Pathfinder] -> FAILED: Path not found.")

    def move_player_by(self, dq: int, dr: int):
        """Перемещает игрока на один гекс в указанном направлении."""
        next_q, next_r = self.player.q + dq, self.player.r + dr

        # Проверка на проходимость
        tile_info = self.get_tile_at_axial(next_q, next_r)
        if tile_info.get("navigation") in [NAV_PASSABLE, "bridge"]:
            self.player.q = next_q
            self.player.r = next_r
            self.player.path = []  # Сбрасываем авто-путь при ручном движении
        else:
            print(
                f"Movement blocked at ({next_q},{next_r}) by {tile_info.get('navigation')}"
            )

    def get_render_state(self) -> Dict[str, Any]:
        return {
            "player_q": self.player.q,
            "player_r": self.player.r,
            "path": self.player.path,
            "world_manager": self.world_manager,
        }

    def _handle_path_movement(self, dt: float):
        if not self.player.path:
            return
        self.player.move_timer += dt
        if self.player.move_timer >= PLAYER_MOVE_SPEED:
            self.player.move_timer = 0
            next_q, next_r = self.player.path.pop(0)
            self.player.q, self.player.r = next_q, next_r
