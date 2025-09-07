# game_engine/game_logic/world.py
from typing import Dict, Any, Tuple

from .player import Player
from pygame_tester.world_manager import WorldManager
from ..algorithms.pathfinding.a_star import find_path
from pygame_tester.config import CHUNK_SIZE, PLAYER_MOVE_SPEED
from ..core.constants import NAV_PASSABLE, KIND_GROUND


class GameWorld:
    def __init__(self, world_seed: int):
        self.world_manager = WorldManager(world_seed)  # <-- Переименовано для ясности
        self.player = Player(wx=CHUNK_SIZE // 2, wz=CHUNK_SIZE // 2)
        self.render_grid_radius = 1
        self.render_grid: Dict[Tuple[int, int], Dict] = {}
        self.last_player_chunk_pos = (-999, -999)
        # --- ИЗМЕНЕНИЕ: Просто обновляем грид при старте ---
        self._update_surrounding_grid(0, 0)

    def update(self, dt: float):
        player_cx = self.player.wx // CHUNK_SIZE
        player_cz = self.player.wz // CHUNK_SIZE
        if (player_cx, player_cz) != self.last_player_chunk_pos:
            self.last_player_chunk_pos = (player_cx, player_cz)
            self._update_surrounding_grid(player_cx, player_cz)

        # --- УДАЛЕНО: вызов _check_world_transition ---
        self._handle_path_movement(dt)

    def _update_surrounding_grid(self, center_cx: int, center_cz: int):
        # --- ИЗМЕНЕНИЕ: Упрощено, всегда работает с процедурным миром ---
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

    # --- УДАЛЕНО: метод _check_world_transition ---

    def get_tile_at(self, wx: int, wz: int) -> Dict:
        cx, cz = wx // CHUNK_SIZE, wz // CHUNK_SIZE
        chunk_data = self.render_grid.get((cx, cz))
        if not chunk_data:
            return {
                "surface": "void",
                "navigation": NAV_PASSABLE,
                "overlay": 0,
                "height": 0,
            }

        lx, lz = wx % CHUNK_SIZE, wz % CHUNK_SIZE
        surface_grid = chunk_data.get("surface", [])
        nav_grid = chunk_data.get("navigation", [])
        overlay_grid = chunk_data.get("overlay", [])  # <-- Добавлено
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
            "surface": surface_grid[lz][lx],
            "navigation": nav_grid[lz][lx],
            "overlay": overlay_grid[lz][lx]
            if (0 <= lz < len(overlay_grid) and 0 <= lx < len(overlay_grid[0]))
            else 0,
            # <-- Добавлено
            "height": height_grid[lz][lx]
            if (0 <= lz < len(height_grid) and 0 <= lx < len(height_grid[0]))
            else 0,
        }

    def set_player_target(self, target_wx: int, target_wz: int):
        player_cx, player_cz = (
            self.player.wx // CHUNK_SIZE,
            self.player.wz // CHUNK_SIZE,
        )
        target_cx, target_cz = target_wx // CHUNK_SIZE, target_wz // CHUNK_SIZE
        min_cx = min(player_cx, target_cx)
        max_cx = max(player_cx, target_cx)
        min_cz = min(player_cz, target_cz)
        max_cz = max(player_cz, target_cz)
        num_chunks_x = max_cx - min_cx + 1
        num_chunks_z = max_cz - min_cz + 1
        stitched_width = num_chunks_x * CHUNK_SIZE
        stitched_height = num_chunks_z * CHUNK_SIZE

        stitched_surface_grid = [
            [KIND_GROUND for _ in range(stitched_width)] for _ in range(stitched_height)
        ]
        stitched_nav_grid = [
            [NAV_PASSABLE for _ in range(stitched_width)]
            for _ in range(stitched_height)
        ]
        # --- ИЗМЕНЕНИЕ: Склеиваем overlay_grid тоже ---
        stitched_overlay_grid = [
            [0 for _ in range(stitched_width)] for _ in range(stitched_height)
        ]
        stitched_height_grid = [
            [0.0 for _ in range(stitched_width)] for _ in range(stitched_height)
        ]

        for cz_offset in range(num_chunks_z):
            for cx_offset in range(num_chunks_x):
                cx, cz = min_cx + cx_offset, min_cz + cz_offset
                chunk_data = self.render_grid.get((cx, cz))
                if chunk_data:
                    paste_x_start = cx_offset * CHUNK_SIZE
                    paste_z_start = cz_offset * CHUNK_SIZE
                    surface = chunk_data.get("surface", [])
                    nav = chunk_data.get("navigation", [])
                    overlay = chunk_data.get("overlay", [])
                    height = chunk_data.get("height", [])
                    if not surface or not nav or not height or not overlay:
                        continue
                    for z in range(CHUNK_SIZE):
                        for x in range(CHUNK_SIZE):
                            stitched_surface_grid[paste_z_start + z][
                                paste_x_start + x
                            ] = surface[z][x]
                            stitched_nav_grid[paste_z_start + z][paste_x_start + x] = (
                                nav[z][x]
                            )
                            stitched_overlay_grid[paste_z_start + z][
                                paste_x_start + x
                            ] = overlay[z][x]
                            stitched_height_grid[paste_z_start + z][
                                paste_x_start + x
                            ] = height[z][x]

        start_stitched = (
            self.player.wx - min_cx * CHUNK_SIZE,
            self.player.wz - min_cz * CHUNK_SIZE,
        )
        goal_stitched = (
            target_wx - min_cz * CHUNK_SIZE,
            target_wz - min_cz * CHUNK_SIZE,
        )

        # Передаем оба слоя в find_path (overlay не нужен для поиска пути)
        stitched_path = find_path(
            stitched_surface_grid,
            stitched_nav_grid,
            stitched_height_grid,
            start_stitched,
            goal_stitched,
        )

        if stitched_path:
            wx_offset = min_cx * CHUNK_SIZE
            wz_offset = min_cz * CHUNK_SIZE
            self.player.path = [
                (lx + wx_offset, lz + wz_offset) for lx, lz in stitched_path
            ]
        else:
            self.player.path = []
            print("Path not found across chunks!")

    def move_player_by(self, dx: int, dz: int):
        self.player.wx += dx
        self.player.wz += dz
        self.player.path = []

    def get_render_state(self) -> Dict[str, Any]:
        return {
            "player_wx": self.player.wx,
            "player_wz": self.player.wz,
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
            next_pos = self.player.path.pop(0)
            self.player.wx, self.player.wz = next_pos
