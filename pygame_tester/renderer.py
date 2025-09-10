# pygame_tester/renderer.py
import pygame
import math
import traceback
from typing import Dict, Tuple

from pygame_tester.config import (
    SCREEN_HEIGHT, SCREEN_WIDTH, PLAYER_COLOR,
    ERROR_COLOR, MENU_WIDTH, BACKGROUND_COLOR, CAMERA_ZOOM_SPEED, VIEWPORT_WIDTH, CAMERA_MOVE_SPEED_PIXELS
)


class Camera:
    """Простая 2D камера для панорамирования и масштабирования."""

    def __init__(self, viewport_width: int, viewport_height: int):
        self.viewport_width = viewport_width
        self.viewport_height = viewport_height
        self.x = 0.0
        self.y = 0.0
        self.zoom = 0.25  # Начнем с отдаленного вида

    def process_inputs(self, dt: float):
        keys = pygame.key.get_pressed()
        move_speed = CAMERA_MOVE_SPEED_PIXELS / self.zoom * dt
        if keys[pygame.K_w]:
            self.y -= move_speed
        if keys[pygame.K_s]:
            self.y += move_speed
        if keys[pygame.K_a]:
            self.x -= move_speed
        if keys[pygame.K_d]:
            self.x += move_speed

    def handle_event(self, event: pygame.event.Event):
        if event.type == pygame.MOUSEWHEEL:
            # Масштабирование относительно курсора
            mouse_x, mouse_y = pygame.mouse.get_pos()
            world_x_before, world_y_before = self.screen_to_world(mouse_x, mouse_y)

            new_zoom = self.zoom + event.y * CAMERA_ZOOM_SPEED * self.zoom
            self.zoom = max(0.05, min(new_zoom, 5.0))

            world_x_after, world_y_after = self.screen_to_world(mouse_x, mouse_y)

            self.x += world_x_before - world_x_after
            self.y += world_y_before - world_y_after

    def screen_to_world(self, sx: int, sy: int) -> Tuple[float, float]:
        world_x = self.x + (sx / self.zoom)
        world_y = self.y + (sy / self.zoom)
        return world_x, world_y

    def world_to_screen(self, wx: float, wy: float) -> Tuple[float, float]:
        screen_x = (wx - self.x) * self.zoom
        screen_y = (wy - self.y) * self.zoom
        return screen_x, screen_y

    def get_visible_world_rect(self) -> pygame.Rect:
        return pygame.Rect(
            self.x, self.y,
            self.viewport_width / self.zoom,
            self.viewport_height / self.zoom
        )


class Renderer:
    def __init__(self, screen):
        self.screen = screen
        self.font = pygame.font.SysFont("consolas", 14)
        self.error_message = None

    def set_error(self, message: str):
        self.error_message = message

    def draw_error_banner(self):
        if not self.error_message: return
        font = pygame.font.SysFont("Arial", 20, bold=True)
        text_surf = font.render(self.error_message, True, (255, 255, 0))
        bg_rect = text_surf.get_rect(center=(VIEWPORT_WIDTH / 2, 30)).inflate(20, 10)
        pygame.draw.rect(self.screen, (100, 0, 0), bg_rect)
        pygame.draw.rect(self.screen, (255, 255, 0), bg_rect, 2)
        self.screen.blit(text_surf, text_surf.get_rect(center=bg_rect.center))

    def draw_player_marker(self, surface: pygame.Surface):
        center_x, center_y = surface.get_width() // 2, surface.get_height() // 2
        pygame.draw.circle(surface, PLAYER_COLOR, (center_x, center_y), 10, 2)
        pygame.draw.line(surface, PLAYER_COLOR, (center_x, center_y - 15), (center_x, center_y + 15), 2)
        pygame.draw.line(surface, PLAYER_COLOR, (center_x - 15, center_y), (center_x + 15, center_y), 2)

    def draw_status(self, camera: Camera, world_map):
        world_x, world_y = camera.x + camera.viewport_width / (2 * camera.zoom), camera.y + camera.viewport_height / (
                    2 * camera.zoom)
        cx, cz = world_map.world_pixel_to_chunk_coords(world_x, world_y)

        status_text = (
            f"Seed: {world_map.seed} | "
            f"Camera World Pos: ({world_x:.0f}, {world_y:.0f}) | "
            f"Current Chunk: ({cx}, {cz}) | "
            f"Zoom: {camera.zoom:.2f}"
        )
        text_surface = self.font.render(status_text, True, (255, 255, 255))
        bar_height = text_surface.get_height() + 8
        s = pygame.Surface((SCREEN_WIDTH, bar_height), pygame.SRCALPHA)
        s.fill((0, 0, 0, 180))
        self.screen.blit(s, (0, SCREEN_HEIGHT - bar_height))
        self.screen.blit(text_surface, (5, SCREEN_HEIGHT - bar_height + 4))