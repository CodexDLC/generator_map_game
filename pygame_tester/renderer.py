# generator_tester/renderer.py
# ... (импорты и классы Camera, Minimap без изменений) ...
import pygame
import pathlib
from typing import List, Tuple, Dict
from .config import (
    TILE_SIZE, SCREEN_HEIGHT, SCREEN_WIDTH, PLAYER_COLOR, PATH_COLOR, ERROR_COLOR, GATEWAY_COLOR,
    VIEWPORT_WIDTH_TILES, VIEWPORT_HEIGHT_TILES, ARTIFACTS_ROOT, CHUNK_SIZE
)
from engine.worldgen_core.base.constants import DEFAULT_PALETTE


class Camera:
    def __init__(self):
        self.top_left_wx = 0
        self.top_left_wz = 0

    def center_on_player(self, player_wx: int, player_wz: int):
        self.top_left_wx = player_wx - VIEWPORT_WIDTH_TILES // 2
        self.top_left_wz = player_wz - VIEWPORT_HEIGHT_TILES // 2


class Minimap:
    def __init__(self, screen):
        self.screen = screen
        self.map_size_chunks = 5
        self.cell_size_px = 32
        self.map_pixel_size = self.map_size_chunks * self.cell_size_px
        self.position = (10, 10)
        self.image_cache: Dict[pathlib.Path, pygame.Surface] = {}

    def _get_preview_image(self, world_manager, cx: int, cz: int) -> pygame.Surface | None:
        path = world_manager._get_chunk_path(world_manager.world_id, world_manager.current_seed, cx, cz) / "preview.png"
        if path in self.image_cache: return self.image_cache[path]
        try:
            image = pygame.image.load(str(path)).convert()
            scaled_image = pygame.transform.scale(image, (self.cell_size_px, self.cell_size_px))
            self.image_cache[path] = scaled_image
            return scaled_image
        except (pygame.error, FileNotFoundError):
            return None

    def draw(self, world_manager, player_cx: int, player_cz: int):
        map_surface = pygame.Surface((self.map_pixel_size, self.map_pixel_size))
        map_surface.fill((20, 20, 30))
        map_surface.set_alpha(200)
        center_offset = self.map_size_chunks // 2
        for y in range(self.map_size_chunks):
            for x in range(self.map_size_chunks):
                chunk_cx = player_cx + x - center_offset
                chunk_cz = player_cz + y - center_offset
                img = self._get_preview_image(world_manager, chunk_cx, chunk_cz)
                if img: map_surface.blit(img, (x * self.cell_size_px, y * self.cell_size_px))
        pygame.draw.rect(map_surface, (100, 100, 120), map_surface.get_rect(), 1)
        player_marker_rect = (center_offset * self.cell_size_px, center_offset * self.cell_size_px, self.cell_size_px,
                              self.cell_size_px)
        pygame.draw.rect(map_surface, (255, 255, 0), player_marker_rect, 2)
        self.screen.blit(map_surface, self.position)


class Renderer:
    def __init__(self, screen):
        self.screen = screen
        self.font = pygame.font.SysFont("consolas", 12)
        self.colors = {k: self._hex_to_rgb(v) for k, v in DEFAULT_PALETTE.items()}
        self.colors['road'] = self._hex_to_rgb("#d2b48c")
        self.colors['void'] = (10, 10, 15)
        self.colors['slope'] = self._hex_to_rgb("#9aa0a6")
        self.minimap = Minimap(screen)

    def _hex_to_rgb(self, s: str) -> Tuple[int, int, int]:
        s = s.lstrip("#")
        return int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16)

    def draw_world(self, camera: Camera, game_world):
        for screen_y in range(VIEWPORT_HEIGHT_TILES):
            for screen_x in range(VIEWPORT_WIDTH_TILES):
                wx = camera.top_left_wx + screen_x
                wz = camera.top_left_wz + screen_y

                tile_info = game_world.get_tile_at(wx, wz)
                kind_name = tile_info.get("kind", "void")
                height_val = tile_info.get("height", 0)

                color = self.colors.get(kind_name, ERROR_COLOR)

                rect_obj = pygame.Rect(screen_x * TILE_SIZE, screen_y * TILE_SIZE, TILE_SIZE, TILE_SIZE)

                pygame.draw.rect(self.screen, color, rect_obj)

                if TILE_SIZE > 15:
                    text_surface = self.font.render(f"{height_val:.0f}", True, (255, 255, 255))
                    text_rect = text_surface.get_rect(center=rect_obj.center)
                    self.screen.blit(text_surface, text_rect)

    def draw_path(self, path: List[Tuple[int, int]], camera: Camera):
        for wx, wz in path:
            screen_x = (wx - camera.top_left_wx) * TILE_SIZE
            screen_y = (wz - camera.top_left_wz) * TILE_SIZE
            rect = (screen_x, screen_y, TILE_SIZE, TILE_SIZE)
            pygame.draw.rect(self.screen, PATH_COLOR, rect)

    def draw_player(self, player_wx: int, player_wz: int, camera: Camera):
        screen_x = (player_wx - camera.top_left_wx) * TILE_SIZE
        screen_y = (player_wz - camera.top_left_wz) * TILE_SIZE
        rect = (screen_x, screen_y, TILE_SIZE, TILE_SIZE)
        pygame.draw.rect(self.screen, PLAYER_COLOR, rect)

    # <<< =============== ИСПРАВЛЕНИЕ ИНТЕРФЕЙСА =============== >>>
    def draw_status(self, world_manager, player_wx, player_wz):
        current_cx = player_wx // CHUNK_SIZE
        current_cz = player_wz // CHUNK_SIZE
        status_text = (f"World: {world_manager.world_id} | "
                       f"Seed: {world_manager.current_seed} | "
                       f"Chunk: ({current_cx}, {current_cz}) | "
                       f"Player: ({player_wx}, {player_wz})")

        status_font = pygame.font.SysFont("consolas", 16)
        text_surface = status_font.render(status_text, True, (255, 255, 255))

        # Создаем фон для текста
        bar_height = text_surface.get_height() + 8
        bar_rect = pygame.Rect(0, SCREEN_HEIGHT - bar_height, SCREEN_WIDTH, bar_height)

        # Рисуем полупрозрачную плашку
        s = pygame.Surface((SCREEN_WIDTH, bar_height), pygame.SRCALPHA)
        s.fill((0, 0, 0, 180))  # Черный, 180/255 прозрачность
        self.screen.blit(s, (0, SCREEN_HEIGHT - bar_height))

        # Рисуем текст поверх плашки
        text_rect = text_surface.get_rect(centery=bar_rect.centery, x=5)
        self.screen.blit(text_surface, text_rect)

    def draw_minimap(self, world_manager, player_cx: int, player_cz: int):
        self.minimap.draw(world_manager, player_cx, player_cz)