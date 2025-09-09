# pygame_tester/renderer.py
import pygame
import math
import sys
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
    MENU_WIDTH,
    BACKGROUND_COLOR,
)
from game_engine.core.constants import DEFAULT_PALETTE
from game_engine.core.grid.hex import HexGridSpec


class Camera:
    def __init__(self, grid_spec: HexGridSpec):
        self.grid_spec = grid_spec
        self.top_left_wx = 0.0
        self.top_left_wz = 0.0

    def center_on_player(self, player_q: int, player_r: int):
        player_wx, player_wz = self.grid_spec.axial_to_world(player_q, player_r)
        self.top_left_wx = player_wx - (SCREEN_WIDTH - MENU_WIDTH) / 2 * self.grid_spec.meters_per_pixel
        self.top_left_wz = player_wz - SCREEN_HEIGHT / 2 * self.grid_spec.meters_per_pixel


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
    def __init__(self, screen, grid_spec: HexGridSpec, camera: Camera):
        self.screen = screen
        self.font = pygame.font.SysFont("consolas", 10)
        self.colors = {k: self._hex_to_rgb(v) for k, v in DEFAULT_PALETTE.items()}
        self.colors["road"] = self._hex_to_rgb("#d2b48c")
        self.colors["void"] = (10, 10, 15)
        self.colors["slope"] = self._hex_to_rgb("#9aa0a6")
        self.layer_mode = "surface"
        self.show_hex_borders = True
        self.error_message = None

        self.grid_spec = grid_spec
        # --- ИСПРАВЛЕНИЕ: Удаляем строку, вызывающую ошибку, т.к. значение уже корректно ---
        self.hex_size_px = TILE_SIZE / 2

        # --- ИСПРАВЛЕНИЕ: Принимаем экземпляр Camera в качестве аргумента ---
        self.camera = camera

        print(f"Renderer initialized:")
        print(f"  edge_m: {self.grid_spec.edge_m}")
        print(f"  meters_per_pixel: {self.grid_spec.meters_per_pixel:.4f}")
        print(f"  hex_size_px (radius): {self.hex_size_px:.2f}")

    def _hex_to_rgb(self, s: str) -> Tuple[int, int, int]:
        s = s.lstrip("#")
        return int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16)

    def _get_screen_rect_from_axial(self, q: int, r: int) -> pygame.Rect:
        world_x, world_z = self.grid_spec.axial_to_world(q, r)
        screen_x = (world_x - self.camera.top_left_wx) / self.grid_spec.meters_per_pixel
        screen_y = (world_z - self.camera.top_left_wz) / self.grid_spec.meters_per_pixel

        rect_x = screen_x - self.hex_size_px
        rect_y = screen_y - self.hex_size_px
        rect_width = self.hex_size_px * 2
        rect_height = self.hex_size_px * 2

        return pygame.Rect(rect_x, rect_y, rect_width, rect_height)

    def set_error(self, message: str):
        self.error_message = message

    def draw_error_banner(self):
        if not self.error_message:
            return

        font = pygame.font.SysFont("Arial", 20)
        text_surf = font.render(self.error_message, True, (255, 255, 0))
        text_rect = text_surf.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2))

        pygame.draw.rect(self.screen, (30, 0, 0), text_rect.inflate(20, 20))
        pygame.draw.rect(self.screen, (255, 255, 0), text_rect.inflate(20, 20), 2)
        self.screen.blit(text_surf, text_rect)

    def draw_world(self, game_world, target_surface: pygame.Surface):
        target_surface.fill(BACKGROUND_COLOR)

        try:
            # Обход по гексам, попадающим в видимую область
            # Это намного эффективнее, чем итерироваться по пикселям
            start_x_m = self.camera.top_left_wx
            start_z_m = self.camera.top_left_wz
            end_x_m = start_x_m + target_surface.get_width() * self.grid_spec.meters_per_pixel
            end_z_m = start_z_m + target_surface.get_height() * self.grid_spec.meters_per_pixel

            start_q, start_r = self.grid_spec.world_to_axial(start_x_m, start_z_m)
            end_q, end_r = self.grid_spec.world_to_axial(end_x_m, end_z_m)

            # Расширяем область поиска на 1 гекс, чтобы избежать артефактов на границах
            for r in range(min(start_r, end_r) - 1, max(start_r, end_r) + 1):
                for q in range(min(start_q, end_q) - 1, max(start_q, end_q) + 1):
                    center_x_w, center_z_w = self.grid_spec.axial_to_world(q, r)

                    if not (start_x_m <= center_x_w <= end_x_m and start_z_m <= center_z_w <= end_z_m):
                        continue

                    center_x_screen = (center_x_w - self.camera.top_left_wx) / self.grid_spec.meters_per_pixel
                    center_y_screen = (center_z_w - self.camera.top_left_wz) / self.grid_spec.meters_per_pixel

                    # Кэшируем углы
                    corners = _get_hex_corners(center_x_screen, center_y_screen, self.hex_size_px)

                    tile_info = game_world.get_tile_at(center_x_w, center_z_w)
                    height_val = tile_info.get("height", 0)

                    color = BACKGROUND_COLOR
                    if self.layer_mode == "surface":
                        surface_kind = tile_info.get("surface", "void")
                        overlay_id = tile_info.get("overlay", 0)
                        color = self.colors.get(surface_kind, ERROR_COLOR)
                        if overlay_id != 0:
                            color = self.colors.get("road", ERROR_COLOR)
                    elif self.layer_mode == "height":
                        color = _get_height_color(height_val, 0, 150)
                    else:  # Для будущего режима temperature
                        color = _get_height_color(height_val, 0, 150)  # Заглушка, использующая высоту

                    pygame.draw.polygon(target_surface, color, corners)

                    if self.show_hex_borders:
                        pygame.draw.polygon(target_surface, (0, 0, 0), corners, 1)
        except Exception as e:
            self.set_error(f"Render Error: {e}")

    def draw_path(
            self,
            path: List[Tuple[int, int]],
            target_surface: pygame.Surface,
    ):
        for q, r in path:
            rect = self._get_screen_rect_from_axial(q, r)
            pygame.draw.rect(target_surface, PATH_COLOR, rect)

    def draw_player(
            self,
            player_q: int,
            player_r: int,
            target_surface: pygame.Surface,
    ):
        rect = self._get_screen_rect_from_axial(player_q, player_r)
        pygame.draw.rect(target_surface, PLAYER_COLOR, rect)

    def draw_status(self, world_manager, player_wx, player_wz):
        chunk_size_m = self.grid_spec.chunk_size_m
        current_cx = int(player_wx // chunk_size_m)
        current_cz = int(player_wz // chunk_size_m)
        status_text = (
            f"World: {world_manager.world_id} | "
            f"Seed: {world_manager.current_seed} | "
            f"Chunk: ({current_cx}, {current_cz}) | "
            f"Player: ({player_wx:.2f}, {player_wz:.2f}) | "
            f"Mode: {self.layer_mode} | "
            f"Borders: {self.show_hex_borders}"
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