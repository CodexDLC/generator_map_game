# generator_tester/renderer.py
import pygame
from typing import List, Tuple
from .config import TILE_SIZE, SCREEN_HEIGHT, PLAYER_COLOR, PATH_COLOR, ERROR_COLOR
from engine.worldgen_core.base.constants import DEFAULT_PALETTE


class Renderer:
    def __init__(self, screen):
        self.screen = screen
        self.font = pygame.font.SysFont("consolas", 16)
        self.colors = {k: self._hex_to_rgb(v) for k, v in DEFAULT_PALETTE.items()}
        # Добавляем недостающие цвета
        self.colors['road'] = self._hex_to_rgb("#d2b48c")

    def _hex_to_rgb(self, s: str) -> Tuple[int, int, int]:
        s = s.lstrip("#")
        if len(s) == 8: s = s[2:]
        return int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16)

    def draw_world(self, kind_grid: List[List[str]]):
        for z, row in enumerate(kind_grid):
            for x, kind_name in enumerate(row):
                color = self.colors.get(kind_name, ERROR_COLOR)
                rect = (x * TILE_SIZE, z * TILE_SIZE, TILE_SIZE, TILE_SIZE)
                pygame.draw.rect(self.screen, color, rect)

    def draw_path(self, path: List[Tuple[int, int]]):
        for pos in path:
            rect = (pos[0] * TILE_SIZE, pos[1] * TILE_SIZE, TILE_SIZE, TILE_SIZE)
            pygame.draw.rect(self.screen, PATH_COLOR, rect)

    def draw_player(self, player_pos: Tuple[int, int]):
        rect = (player_pos[0] * TILE_SIZE, player_pos[1] * TILE_SIZE, TILE_SIZE, TILE_SIZE)
        pygame.draw.rect(self.screen, PLAYER_COLOR, rect)

    def draw_status(self, world_manager):
        status_text = (f"World: {world_manager.world_id} | "
                       f"Seed: {world_manager.current_seed} | "
                       f"Coords: ({world_manager.cx}, {world_manager.cz})")
        text_surface = self.font.render(status_text, True, (255, 255, 255))
        self.screen.blit(text_surface, (5, SCREEN_HEIGHT - 20))