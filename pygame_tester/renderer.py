# pygame_tester/renderer.py
import pygame
import math
import traceback
from typing import List, Tuple, Dict

from game_engine_restructured.core.constants import DEFAULT_PALETTE
from game_engine_restructured.core.grid.hex import HexGridSpec
from .config import (
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
    PLAYER_COLOR,
    PATH_COLOR,
    ERROR_COLOR,
    MENU_WIDTH,
    BACKGROUND_COLOR, TILE_SIZE,
)



class Camera:
    def __init__(self, grid_spec: HexGridSpec):
        self.grid_spec = grid_spec
        self.top_left_wx = 0.0
        self.top_left_wz = 0.0
        self.zoom = 1.0

    def center_on_player(self, player_q: int, player_r: int):
        player_wx, player_wz = self.grid_spec.axial_to_world(player_q, player_r)

        meters_per_screen_pixel = self.grid_spec.edge_m / (TILE_SIZE / 2.0 * self.zoom)

        viewport_width_m = (SCREEN_WIDTH - MENU_WIDTH) * meters_per_screen_pixel
        viewport_height_m = SCREEN_HEIGHT * meters_per_screen_pixel

        self.top_left_wx = player_wx - viewport_width_m / 2
        self.top_left_wz = player_wz - viewport_height_m / 2

    def move_by_pixels(self, dx: float, dz: float):
        meters_per_screen_pixel = self.grid_spec.edge_m / (TILE_SIZE / 2.0 * self.zoom)
        self.top_left_wx += dx * meters_per_screen_pixel
        self.top_left_wz += dz * meters_per_screen_pixel

    def change_zoom(self, amount: float, mouse_pos: Tuple[int, int]):

        self.zoom += amount
        self.zoom = max(0.2, min(self.zoom, 5.0))


def _get_hex_corners(center_x: float, center_y: float, size: float) -> List[Tuple[float, float]]:
    corners = []
    for i in range(6):
        angle_deg = 60 * i + 30
        angle_rad = math.pi / 180 * angle_deg
        x = center_x + size * math.cos(angle_rad)
        y = center_y + size * math.sin(angle_rad)
        corners.append((x, y))
    return corners


def _get_height_color(height: float, min_h: float, max_h: float) -> Tuple[int, int, int]:
    if max_h <= min_h: return (128, 128, 128)
    norm_h = max(0.0, min(1.0, (height - min_h) / (max_h - min_h)))
    c = int(255 * norm_h)
    return (c, c, c)


class Renderer:
    def __init__(self, screen, grid_spec: HexGridSpec, camera: Camera):
        self.screen = screen
        self.font = pygame.font.SysFont("consolas", 14)
        self.colors = {k: self._hex_to_rgb(v) for k, v in DEFAULT_PALETTE.items()}
        self.colors["void"] = BACKGROUND_COLOR
        self.layer_mode = "surface"
        self.show_hex_borders = True
        self.error_message = None

        self.grid_spec = grid_spec
        self.camera = camera
        self.hex_pixel_radius_at_zoom_1 = TILE_SIZE / 2.0

    def _hex_to_rgb(self, s: str) -> Tuple[int, int, int]:
        s = s.lstrip("#")
        return int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16)

    def _world_to_screen(self, wx: float, wz: float) -> Tuple[float, float]:
        pixels_per_meter = (self.hex_pixel_radius_at_zoom_1 / self.grid_spec.edge_m) * self.camera.zoom
        sx = (wx - self.camera.top_left_wx) * pixels_per_meter
        sz = (wz - self.camera.top_left_wz) * pixels_per_meter
        return sx, sz

    def screen_to_world(self, sx: float, sz: float) -> Tuple[float, float]:
        meters_per_screen_pixel = self.grid_spec.edge_m / (self.hex_pixel_radius_at_zoom_1 * self.camera.zoom)
        wx = self.camera.top_left_wx + sx * meters_per_screen_pixel
        wz = self.camera.top_left_wz + sz * meters_per_screen_pixel
        return wx, wz

    def set_error(self, message: str):
        self.error_message = message

    def draw_error_banner(self):
        if not self.error_message: return
        font = pygame.font.SysFont("Arial", 20, bold=True)
        text_surf = font.render(self.error_message, True, (255, 255, 0))
        bg_rect = text_surf.get_rect(center=((SCREEN_WIDTH - MENU_WIDTH) / 2, 30)).inflate(20, 10)
        pygame.draw.rect(self.screen, (100, 0, 0), bg_rect)
        pygame.draw.rect(self.screen, (255, 255, 0), bg_rect, 2)
        self.screen.blit(text_surf, text_surf.get_rect(center=bg_rect.center))

    def draw_world(self, game_world, target_surface: pygame.Surface):
        target_surface.fill(BACKGROUND_COLOR)
        try:
            # --- ИЗМЕНЕНИЕ: Умное определение области отрисовки ---

            # 1. Находим мировые координаты 4 углов экрана
            meters_per_px = self.grid_spec.edge_m / (self.hex_pixel_radius_at_zoom_1 * self.camera.zoom)
            viewport_w_m = target_surface.get_width() * meters_per_px
            viewport_h_m = target_surface.get_height() * meters_per_px

            wx_start, wz_start = self.camera.top_left_wx, self.camera.top_left_wz
            wx_end, wz_end = wx_start + viewport_w_m, wz_start + viewport_h_m

            # 2. Находим гексагональные координаты этих 4 углов
            corners_axial = [
                self.grid_spec.world_to_axial(wx_start, wz_start),
                self.grid_spec.world_to_axial(wx_end, wz_start),
                self.grid_spec.world_to_axial(wx_start, wz_end),
                self.grid_spec.world_to_axial(wx_end, wz_end),
            ]

            # 3. Находим минимальные и максимальные q и r из этих 4 точек
            min_q = min(c[0] for c in corners_axial)
            max_q = max(c[0] for c in corners_axial)
            min_r = min(c[1] for c in corners_axial)
            max_r = max(c[1] for c in corners_axial)

            # 4. Итерируемся по этому большому прямоугольнику, который гарантированно покроет экран
            for r in range(min_r - 1, max_r + 2):
                for q in range(min_q - 1, max_q + 2):
                    # (Дальнейшая логика отрисовки остается той же)
                    tile_info = game_world.get_tile_at_axial(q, r)
                    if tile_info["surface"] == "void": continue

                    color = self.colors.get(tile_info["surface"], ERROR_COLOR)

                    if self.layer_mode == "surface":
                        if tile_info.get("overlay", 0) != 0:
                            color = self.colors.get("road", ERROR_COLOR)
                    elif self.layer_mode == "height":
                        color = _get_height_color(tile_info.get("height", 0), 0, 150)

                    wx, wz = self.grid_spec.axial_to_world(q, r)
                    sx, sz = self._world_to_screen(wx, wz)

                    current_hex_pixel_radius = self.hex_pixel_radius_at_zoom_1 * self.camera.zoom
                    corners = _get_hex_corners(sx, sz, current_hex_pixel_radius)

                    pygame.draw.polygon(target_surface, color, corners)
                    if self.show_hex_borders:
                        pygame.draw.polygon(target_surface, (50, 50, 50), corners, 1)

        except Exception as e:
            self.set_error(f"Render Error: {e}")
            traceback.print_exc()

    def draw_path(self, path: List[Tuple[int, int]], target_surface: pygame.Surface):
        if not path or len(path) < 2: return
        points = [self._world_to_screen(*self.grid_spec.axial_to_world(q, r)) for q, r in path]
        pygame.draw.lines(target_surface, PATH_COLOR, False, points, 3)

    def draw_player(self, player_q: int, player_r: int, target_surface: pygame.Surface):
        wx, wz = self.grid_spec.axial_to_world(player_q, player_r)
        sx, sz = self._world_to_screen(wx, wz)
        player_radius = self.hex_pixel_radius_at_zoom_1 * self.camera.zoom * 0.6
        pygame.draw.circle(target_surface, PLAYER_COLOR, (sx, sz), player_radius)
        pygame.draw.circle(target_surface, (0, 0, 0), (sx, sz), player_radius, 2)

    def draw_status(self, world_manager, player_wx, player_wz, player_q, player_r):
        current_cx, current_cz = self.grid_spec.axial_to_chunk_coords(player_q, player_r)
        status_text = (
            f"Seed: {world_manager.current_seed} | "
            f"Chunk: ({current_cx}, {current_cz}) | "
            f"Player W: ({player_wx:.1f}, {player_wz:.1f}) | "
            f"Q,R: ({player_q}, {player_r}) | "
            f"Zoom: {self.camera.zoom:.2f} | "
            f"Mode: {self.layer_mode.capitalize()}"
        )
        text_surface = self.font.render(status_text, True, (255, 255, 255))
        bar_height = text_surface.get_height() + 8
        s = pygame.Surface((SCREEN_WIDTH, bar_height), pygame.SRCALPHA)
        s.fill((0, 0, 0, 180))
        self.screen.blit(s, (0, SCREEN_HEIGHT - bar_height))
        self.screen.blit(text_surface, (5, SCREEN_HEIGHT - bar_height + 4))