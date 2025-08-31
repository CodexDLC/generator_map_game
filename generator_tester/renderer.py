# generator_tester/renderer.py
import pygame
from typing import List, Tuple
from .config import TILE_SIZE, SCREEN_HEIGHT, PLAYER_COLOR, PATH_COLOR, ERROR_COLOR, GATEWAY_COLOR, \
    VIEWPORT_WIDTH_TILES, VIEWPORT_HEIGHT_TILES
from engine.worldgen_core.base.constants import DEFAULT_PALETTE


class Camera:
    """Простая камера, которая следует за мировыми координатами игрока."""

    def __init__(self):
        # top_left_wx/wz - это мировые координаты тайла в левом верхнем углу экрана
        self.top_left_wx = 0
        self.top_left_wz = 0

    def center_on_player(self, player_wx: int, player_wz: int):
        self.top_left_wx = player_wx - VIEWPORT_WIDTH_TILES // 2
        self.top_left_wz = player_wz - VIEWPORT_HEIGHT_TILES // 2


class Renderer:
    def __init__(self, screen):
        self.screen = screen
        self.font = pygame.font.SysFont("consolas", 16)
        self.colors = {k: self._hex_to_rgb(v) for k, v in DEFAULT_PALETTE.items()}
        self.colors['road'] = self._hex_to_rgb("#d2b48c")

    def _hex_to_rgb(self, s: str) -> Tuple[int, int, int]:
        s = s.lstrip("#")
        if len(s) == 8: s = s[2:]
        return int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16)

    def draw_world(self, camera: Camera, world_manager):
        """Отрисовывает видимую часть мира на основе положения камеры."""
        for screen_y in range(VIEWPORT_HEIGHT_TILES):
            for screen_x in range(VIEWPORT_WIDTH_TILES):
                # Рассчитываем мировые координаты для каждого пикселя на экране
                wx = camera.top_left_wx + screen_x
                wz = camera.top_left_wz + screen_y

                # Получаем данные о тайле из WorldManager
                tile_info = world_manager.get_tile_at(wx, wz)
                kind_name = tile_info.get("kind", "void")

                color = self.colors.get(kind_name, ERROR_COLOR)
                rect = (screen_x * TILE_SIZE, screen_y * TILE_SIZE, TILE_SIZE, TILE_SIZE)
                pygame.draw.rect(self.screen, color, rect)

                # <<< НОВОЕ: Отрисовка шлюзов в городе >>>
                if tile_info.get("is_gateway"):
                    pygame.draw.circle(self.screen, GATEWAY_COLOR, rect.center, TILE_SIZE // 2, 1)

    def draw_path(self, path: List[Tuple[int, int]], camera: Camera):
        for wx, wz in path:
            # Преобразуем мировые координаты пути в экранные
            screen_x = (wx - camera.top_left_wx) * TILE_SIZE
            screen_y = (wz - camera.top_left_wz) * TILE_SIZE
            rect = (screen_x, screen_y, TILE_SIZE, TILE_SIZE)
            pygame.draw.rect(self.screen, PATH_COLOR, rect)

    def draw_player(self, player_wx: int, player_wz: int, camera: Camera):
        # Преобразуем мировые координаты игрока в экранные
        screen_x = (player_wx - camera.top_left_wx) * TILE_SIZE
        screen_y = (player_wz - camera.top_left_wz) * TILE_SIZE
        rect = (screen_x, screen_y, TILE_SIZE, TILE_SIZE)
        pygame.draw.rect(self.screen, PLAYER_COLOR, rect)

    def draw_status(self, world_manager, player_wx, player_wz):
        status_text = (f"World: {world_manager.world_id} | "
                       f"Seed: {world_manager.current_seed} | "
                       f"Chunk: ({world_manager.cx}, {world_manager.cz}) | "
                       f"Player: ({player_wx}, {player_wz})")
        text_surface = self.font.render(status_text, True, (255, 255, 255))
        self.screen.blit(text_surface, (5, SCREEN_HEIGHT - 20))