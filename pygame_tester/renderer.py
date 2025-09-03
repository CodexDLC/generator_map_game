# pygame_tester/renderer.py
import pygame
from typing import List, Tuple, Dict
from .config import (
    TILE_SIZE, SCREEN_HEIGHT, SCREEN_WIDTH, PLAYER_COLOR, PATH_COLOR, ERROR_COLOR,
    VIEWPORT_WIDTH_TILES, VIEWPORT_HEIGHT_TILES, CHUNK_SIZE
)
from game_engine.core.constants import DEFAULT_PALETTE


class Camera:
    def __init__(self):
        self.top_left_wx = 0
        self.top_left_wz = 0

    def center_on_player(self, player_wx: int, player_wz: int):
        self.top_left_wx = player_wx - VIEWPORT_WIDTH_TILES // 2
        self.top_left_wz = player_wz - VIEWPORT_HEIGHT_TILES // 2


# --- НАЧАЛО ИЗМЕНЕНИЯ: Удаляем Minimap из этого файла, мы перенесем ее в ui.py ---
# class Minimap: ... (ВЕСЬ КЛАСС УДАЛЕН)
# --- КОНЕЦ ИЗМЕНЕНИЯ ---


class Renderer:
    def __init__(self, screen):
        self.screen = screen
        # --- НАЧАЛО ИЗМЕНЕНИЯ: Уменьшаем шрифт, чтобы текст помещался ---
        self.font = pygame.font.SysFont("consolas", 10) # Изменили размер с 12 на 11
        # --- КОНЕЦ ИЗМЕНЕНИЯ ---
        self.colors = {k: self._hex_to_rgb(v) for k, v in DEFAULT_PALETTE.items()}
        self.colors['road'] = self._hex_to_rgb("#d2b48c")
        self.colors['void'] = (10, 10, 15)
        self.colors['slope'] = self._hex_to_rgb("#9aa0a6")

    def _hex_to_rgb(self, s: str) -> Tuple[int, int, int]:
        s = s.lstrip("#")
        return int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16)
    # --- НАЧАЛО ИЗМЕНЕНИЯ: Методы теперь принимают target_surface ---
    def draw_world(self, camera: Camera, game_world, target_surface: pygame.Surface):
        target_surface.fill(ERROR_COLOR)  # Заполняем фон, чтобы видеть, где наша поверхность
        for screen_y in range(VIEWPORT_HEIGHT_TILES):
            for screen_x in range(VIEWPORT_WIDTH_TILES):
                wx = camera.top_left_wx + screen_x
                wz = camera.top_left_wz + screen_y

                tile_info = game_world.get_tile_at(wx, wz)
                kind_name = tile_info.get("kind", "void")
                height_val = tile_info.get("height", 0)

                # --- ИЗМЕНЕНИЕ: Возвращаем простой, однотонный цвет по типу тайла ---
                color = self.colors.get(kind_name, ERROR_COLOR)

                rect_obj = pygame.Rect(screen_x * TILE_SIZE, screen_y * TILE_SIZE, TILE_SIZE, TILE_SIZE)
                pygame.draw.rect(target_surface, color, rect_obj)

                # Рисуем текст с высотой (с тенью для лучшей читаемости)
                if TILE_SIZE > 15:
                    text_str = f"{height_val:.1f}"

                    # Тень (черный текст со смещением)
                    shadow_pos = rect_obj.centerx + 1, rect_obj.centery + 1
                    shadow_surf = self.font.render(text_str, True, (0, 0, 0))
                    shadow_rect = shadow_surf.get_rect(center=shadow_pos)
                    target_surface.blit(shadow_surf, shadow_rect)

                    # Основной текст (белый)
                    text_surf = self.font.render(text_str, True, (255, 255, 255))
                    text_rect = text_surf.get_rect(center=rect_obj.center)
                    target_surface.blit(text_surf, text_rect)

    def draw_path(self, path: List[Tuple[int, int]], camera: Camera, target_surface: pygame.Surface):
        for wx, wz in path:
            screen_x = (wx - camera.top_left_wx) * TILE_SIZE
            screen_y = (wz - camera.top_left_wz) * TILE_SIZE
            rect = (screen_x, screen_y, TILE_SIZE, TILE_SIZE)
            pygame.draw.rect(target_surface, PATH_COLOR, rect)

    def draw_player(self, player_wx: int, player_wz: int, camera: Camera, target_surface: pygame.Surface):
        screen_x = (player_wx - camera.top_left_wx) * TILE_SIZE
        screen_y = (player_wz - camera.top_left_wz) * TILE_SIZE
        rect = (screen_x, screen_y, TILE_SIZE, TILE_SIZE)
        pygame.draw.rect(target_surface, PLAYER_COLOR, rect)

    # --- КОНЕЦ ИЗМЕНЕНИЯ ---

    def draw_status(self, world_manager, player_wx, player_wz):
        current_cx = player_wx // CHUNK_SIZE
        current_cz = player_wz // CHUNK_SIZE
        status_text = (f"World: {world_manager.world_id} | "
                       f"Seed: {world_manager.current_seed} | "
                       f"Chunk: ({current_cx}, {current_cz}) | "
                       f"Player: ({player_wx}, {player_wz})")

        status_font = pygame.font.SysFont("consolas", 16)
        text_surface = status_font.render(status_text, True, (255, 255, 255))
        bar_height = text_surface.get_height() + 8
        bar_rect = pygame.Rect(0, SCREEN_HEIGHT - bar_height, SCREEN_WIDTH, bar_height)

        s = pygame.Surface((SCREEN_WIDTH, bar_height), pygame.SRCALPHA)
        s.fill((0, 0, 0, 180))
        self.screen.blit(s, (0, SCREEN_HEIGHT - bar_height))

        text_rect = text_surface.get_rect(centery=bar_rect.centery, x=5)
        self.screen.blit(text_surface, text_rect)

    # --- НАЧАЛО ИЗМЕНЕНИЯ: Удаляем draw_minimap ---
    # def draw_minimap(...): ...
    # --- КОНЕЦ ИЗМЕНЕНИЯ ---