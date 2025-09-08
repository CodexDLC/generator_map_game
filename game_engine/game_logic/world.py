# game_engine/game_logic/world.py
from typing import Dict, Any, Tuple, List
import math

from .player import Player
from pygame_tester.world_manager import WorldManager
from ..algorithms.pathfinding.a_star import find_path
from pygame_tester.config import CHUNK_SIZE, PLAYER_MOVE_SPEED
from ..core.constants import NAV_PASSABLE, KIND_GROUND
from ..core.grid.hex import HexGridSpec

class GameWorld:
    def __init__(self, world_seed: int):
        self.world_manager = WorldManager(world_seed)
        self.grid_spec = HexGridSpec(
            edge_m=0.63,
            meters_per_pixel=0.8,
            chunk_px=CHUNK_SIZE
        )
        initial_wx = self.grid_spec.chunk_size_m / 2
        initial_wz = self.grid_spec.chunk_size_m / 2
        initial_q, initial_r = self.grid_spec.world_to_axial(initial_wx, initial_wz)
        self.player = Player(q=initial_q, r=initial_r)
        self.render_grid_radius = 1
        self.render_grid: Dict[Tuple[int, int], Dict] = {}
        self.last_player_chunk_pos = (-999, -999)
        self._update_surrounding_grid(0, 0)

    def update(self, dt: float):
        player_wx, player_wz = self.grid_spec.axial_to_world(self.player.q, self.player.r)
        player_cx = int(player_wx) // CHUNK_SIZE
        player_cz = int(player_wz) // CHUNK_SIZE

        if (player_cx, player_cz) != self.last_player_chunk_pos:
            self.last_player_chunk_pos = (player_cx, player_cz)
            self._update_surrounding_grid(player_cx, player_cz)

        self._handle_path_movement(dt)

    def _update_surrounding_grid(self, center_cx: int, center_cz: int):
        needed_chunks = set()
        for dz in range(-self.render_grid_radius, self.render_grid_radius + 1):
            for dx in range(-self.render_grid_radius, self.render_grid_radius + 1):
                needed_chunks.add((center_cx + dx, center_cz + dz))
        current_chunks_pos = set(self.render_grid.keys())
        for pos in current_chunks_pos - needed_chunks:
            del self.render_grid[pos]
        for pos in needed_chunks:
            self._load_and_render_chunk_at(pos)

    def _load_and_render_chunk_at(self, pos: Tuple[int, int]):
        if pos in self.render_grid:
            return
        chunk_data = self.world_manager.get_chunk_data(pos[0], pos[1])
        if chunk_data:
            self.render_grid[pos] = chunk_data

    def get_tile_at(self, wx: float, wz: float) -> Dict:
        q, r = self.grid_spec.world_to_axial(wx, wz)

        chunk_data = self.world_manager.get_chunk_data(q, r)

        if not chunk_data:
            return {
                "surface": "void",
                "navigation": NAV_PASSABLE,
                "overlay": 0,
                "height": 0,
            }

        lx, lz = self.grid_spec.world_to_px(wx, wz)

        surface_grid = chunk_data.get("surface", [])
        nav_grid = chunk_data.get("navigation", [])
        overlay_grid = chunk_data.get("overlay", [])
        height_grid = chunk_data.get("height", [])

        is_in_bounds = 0 <= lz < len(surface_grid) and 0 <= lx < len(surface_grid[0])
        if not is_in_bounds:
            return {
                "surface": "void",
                "navigation": NAV_PASSABLE,
                "overlay": 0,
                "height": 0,
            }

        return {
            "surface": surface_grid[int(lz)][int(lx)],
            "navigation": nav_grid[int(lz)][int(lx)],
            "overlay": overlay_grid[int(lz)][int(lx)]
            if (0 <= lz < len(overlay_grid) and 0 <= lx < len(overlay_grid[0]))
            else 0,
            "height": height_grid[int(lz)][int(lx)]
            if (0 <= lz < len(height_grid) and 0 <= lx < len(height_grid[0]))
            else 0,
        }

    def set_player_target(self, target_wx: float, target_wz: float):
        start_q, start_r = self.player.q, self.player.r
        goal_q, goal_r = self.grid_spec.world_to_axial(target_wx, target_wz)

        # Получаем данные чанка
        start_chunk_key = (start_q // CHUNK_SIZE, start_r // CHUNK_SIZE)
        goal_chunk_key = (goal_q // CHUNK_SIZE, goal_r // CHUNK_SIZE)

        # Логика сшивания чанков здесь
        # ...

        # Это временно, пока мы не реализуем сшивание чанков для гексов
        self.player.path = find_path(
            self.world_manager.get_chunk_data(0, 0)["surface"],
            self.world_manager.get_chunk_data(0, 0)["navigation"],
            self.world_manager.get_chunk_data(0, 0)["height"],
            (start_q, start_r),
            (goal_q, goal_r)
        )
        if not self.player.path:
            print("Path not found!")

    def move_player_by(self, dq: int, dr: int):
        self.player.q += dq
        self.player.r += dr
        self.player.path = []

    def get_render_state(self) -> Dict[str, Any]:
        return {
            "player_q": self.player.q,
            "player_r": self.player.r,
            "path": self.player.path,
            "world_manager": self.world_manager,
            "game_world": self,
        }

    def _handle_path_movement(self, dt: float):
        if not self.player.path:
            return
        self.player.move_timer += dt
        if self.player.move_timer >= PLAYER_MOVE_SPEED:
            self.player.move_timer = 0
            next_q, next_r = self.player.path.pop(0)
            self.player.q, self.player.r = next_q, next_r