# pygame_tester/renderer.py
import pygame
import math
from typing import List, Tuple, Dict
from .config import (
    TILE_SIZE,
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
    PLAYER_COLOR,
    PATH_COLOR,
    ERROR_COLOR,
    VIEWPORT_WIDTH_TILES,
    VIEWPORT_HEIGHT_TILES,
    CHUNK_SIZE,
    MENU_WIDTH,
)
from game_engine.core.constants import DEFAULT_PALETTE
from game_engine.core.grid.hex import HexGridSpec


class Camera:
    def __init__(self):
        self.top_left_wx = 0.0
        self.top_left_wz = 0.0

    def center_on_player(self, player_q: int, player_r: int, grid_spec: HexGridSpec):
        player_wx, player_wz = grid_spec.axial_to_world(player_q, player_r)
        self.top_left_wx = player_wx - (SCREEN_WIDTH - MENU_WIDTH) / 2
        self.top_left_wz = player_wz - SCREEN_HEIGHT / 2


def _get_height_color(height: float, min_h: float, max_h: float) -> Tuple[int, int, int]:
    if max_h == min_h:
        return (128, 128, 128)
    norm_h = (height - min_h) / (max_h - min_h)
    norm_h = max(0.0, min(1.0, norm_h))
    c = int(255 * norm_h)
    return (c, c, c)


def _get_hex_corners(center_x: float, center_y: float, size: float) -> List[Tuple[float, float]]:
    corners = []
    for i in range(6):
        angle_deg = 60 * i + 30
        angle_rad = math.pi / 180 * angle_deg
        x = center_x + size * math.cos(angle_rad)
        y = center_y + size * math.sin(angle_rad)
        corners.append((x, y))
    return corners


class Renderer:
    def __init__(self, screen):
        self.screen = screen
        self.font = pygame.font.SysFont("consolas", 10)
        self.colors = {k: self._hex_to_rgb(v) for k, v in DEFAULT_PALETTE.items()}
        self.colors["road"] = self._hex_to_rgb("#d2b48c")
        self.colors["void"] = (10, 10, 15)
        self.colors["slope"] = self._hex_to_rgb("#9aa0a6")
        self.debug_mode = False
        self.camera = Camera()
        self.hex_grid_spec = HexGridSpec(0.63, 0.8, CHUNK_SIZE)
        self.hex_size_px = self.hex_grid_spec.edge_m * self.hex_grid_spec.meters_per_pixel / 2

    def _hex_to_rgb(self, s: str) -> Tuple[int, int, int]:
        s = s.lstrip("#")
        return int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16)

    def draw_world(self, game_world, target_surface: pygame.Surface):
        target_surface.fill(ERROR_COLOR)

        for screen_y in range(VIEWPORT_HEIGHT_TILES):
            for screen_x in range(VIEWPORT_WIDTH_TILES):
                world_x = self.camera.top_left_wx + screen_x * self.hex_grid_spec.meters_per_pixel
                world_z = self.camera.top_left_wz + screen_y * self.hex_grid_spec.meters_per_pixel

                q, r = self.hex_grid_spec.world_to_axial(world_x, world_z)
                center_x, center_z = self.hex_grid_spec.axial_to_world(q, r)

                center_x_screen = (center_x - self.camera.top_left_wx) / self.hex_grid_spec.meters_per_pixel
                center_y_screen = (center_z - self.camera.top_left_wz) / self.hex_grid_spec.meters_per_pixel

                tile_info = game_world.get_tile_at(center_x, center_z)
                height_val = tile_info.get("height", 0)

                if self.debug_mode:
                    color = _get_height_color(height_val, 0, 150)
                else:
                    surface_kind = tile_info.get("surface", "void")
                    overlay_id = tile_info.get("overlay", 0)
                    color = self.colors.get(surface_kind, ERROR_COLOR)
                    if overlay_id != 0:
                        color = self.colors.get("road", ERROR_COLOR)

                corners = _get_hex_corners(center_x_screen, center_y_screen, self.hex_size_px)
                pygame.draw.polygon(target_surface, color, corners)
                pygame.draw.polygon(target_surface, (0, 0, 0), corners, 1)

    def draw_path(
            self,
            path: List[Tuple[int, int]],
            target_surface: pygame.Surface,
    ):
        for q, r in path:
            world_x, world_z = self.hex_grid_spec.axial_to_world(q, r)
            screen_x = (world_x - self.camera.top_left_wx) / self.hex_grid_spec.meters_per_pixel
            screen_y = (world_z - self.camera.top_left_wz) / self.hex_grid_spec.meters_per_pixel

            rect_x = screen_x - self.hex_size_px
            rect_y = screen_y - self.hex_size_px
            rect_width = self.hex_size_px * 2
            rect_height = self.hex_size_px * 2

            rect = (rect_x, rect_y, rect_width, rect_height)
            pygame.draw.rect(target_surface, PATH_COLOR, rect)

    def draw_player(
            self,
            player_q: int,
            player_r: int,
            target_surface: pygame.Surface,
    ):
        world_x, world_z = self.hex_grid_spec.axial_to_world(player_q, player_r)
        screen_x = (world_x - self.camera.top_left_wx) / self.hex_grid_spec.meters_per_pixel
        screen_y = (world_z - self.camera.top_left_wz) / self.hex_grid_spec.meters_per_pixel

        rect_x = screen_x - self.hex_size_px
        rect_y = screen_y - self.hex_size_px
        rect_width = self.hex_size_px * 2
        rect_height = self.hex_size_px * 2

        rect = (rect_x, rect_y, rect_width, rect_height)
        pygame.draw.rect(target_surface, PLAYER_COLOR, rect)

    def draw_status(self, world_manager, player_wx, player_wz):
        current_cx = int(player_wx) // CHUNK_SIZE
        current_cz = int(player_wz) // CHUNK_SIZE
        status_text = (
            f"World: {world_manager.world_id} | "
            f"Seed: {world_manager.current_seed} | "
            f"Chunk: ({current_cx}, {current_cz}) | "
            f"Player: ({player_wx:.2f}, {player_wz:.2f})"
        )

        status_font = pygame.font.SysFont("consolas", 16)
        text_surface = status_font.render(status_text, True, (255, 255, 255))
        bar_height = text_surface.get_height() + 8
        bar_rect = pygame.Rect(0, SCREEN_HEIGHT - bar_height, SCREEN_WIDTH, bar_height)

        s = pygame.Surface((SCREEN_WIDTH, bar_height), pygame.SRCALPHA)
        s.fill((0, 0, 0, 180))
        self.screen.blit(s, (0, SCREEN_HEIGHT - bar_height))

        text_rect = text_surface.get_rect(centery=bar_rect.centery, x=5)
        self.screen.blit(text_surface, text_rect)