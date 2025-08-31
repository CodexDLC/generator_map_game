# generator_tester/renderer.py
import pathlib

import pygame
from typing import List, Tuple, Dict
from .config import TILE_SIZE, SCREEN_HEIGHT, PLAYER_COLOR, PATH_COLOR, ERROR_COLOR, GATEWAY_COLOR, \
    VIEWPORT_WIDTH_TILES, VIEWPORT_HEIGHT_TILES, CHUNK_SIZE, ARTIFACTS_ROOT
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


class Minimap:
    """Отрисовывает миникарту на основе превью чанков."""

    def __init__(self, screen):
        self.screen = screen
        self.map_size_chunks = 5  # Размер карты в чанках (5x5)
        self.cell_size_px = 32  # Размер одной ячейки-чанка на карте в пикселях
        self.map_pixel_size = self.map_size_chunks * self.cell_size_px
        self.position = (10, 10)  # Позиция миникарты на экране
        self.image_cache: Dict[pathlib.Path, pygame.Surface] = {}

    def _get_preview_image(self, world_id: str, seed: int, cx: int, cz: int) -> pygame.Surface | None:
        world_parts = world_id.split('/')
        path = ARTIFACTS_ROOT / "world" / pathlib.Path(*world_parts) / str(seed) / f"{cx}_{cz}" / "preview.png"

        if path in self.image_cache:
            return self.image_cache[path]

        # ---> САМЫЙ НАДЕЖНЫЙ СПОСОБ <---
        # Мы не проверяем заранее, а сразу пытаемся загрузить.
        # Если файла нет, ловим ошибку и спокойно выходим.
        try:
            image = pygame.image.load(str(path)).convert()
            scaled_image = pygame.transform.scale(image, (self.cell_size_px, self.cell_size_px))
            self.image_cache[path] = scaled_image
            return scaled_image
        except (pygame.error, FileNotFoundError):
            # Ловим И ошибку Pygame (если файл поврежден),
            # И ошибку отсутствия файла (если он еще не создан).
            return None


    def draw(self, world_manager, player_cx: int, player_cz: int):
        # Поверхность для самой карты
        map_surface = pygame.Surface((self.map_pixel_size, self.map_pixel_size))
        map_surface.fill((20, 20, 30))  # Фон
        map_surface.set_alpha(200)  # Прозрачность

        # Рассчитываем, какой чанк будет в центре карты
        center_offset = self.map_size_chunks // 2

        for y in range(self.map_size_chunks):
            for x in range(self.map_size_chunks):
                # Мировые координаты чанка для этой ячейки карты
                chunk_cx = player_cx + x - center_offset
                chunk_cz = player_cz + y - center_offset

                img = self._get_preview_image(world_manager.world_id, world_manager.current_seed, chunk_cx, chunk_cz)
                if img:
                    map_surface.blit(img, (x * self.cell_size_px, y * self.cell_size_px))

        # Рисуем рамку вокруг карты
        pygame.draw.rect(map_surface, (100, 100, 120), map_surface.get_rect(), 1)

        # Рисуем маркер игрока в центральной ячейке
        player_marker_rect = (center_offset * self.cell_size_px, center_offset * self.cell_size_px, self.cell_size_px,
                              self.cell_size_px)
        pygame.draw.rect(map_surface, (255, 255, 0), player_marker_rect, 2)

        # Отображаем карту на основном экране
        self.screen.blit(map_surface, self.position)

class Renderer:
    def __init__(self, screen):
        self.screen = screen
        self.font = pygame.font.SysFont("consolas", 16)
        self.colors = {k: self._hex_to_rgb(v) for k, v in DEFAULT_PALETTE.items()}
        self.colors['road'] = self._hex_to_rgb("#d2b48c")
        self.minimap = Minimap(screen)  # <-- Создаем экземпляр миникарты

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

                # ---> ИЗМЕНЕНИЕ ЗДЕСЬ <---
                # Создаем объект pygame.Rect, чтобы у него был атрибут .center
                rect = pygame.Rect(screen_x * TILE_SIZE, screen_y * TILE_SIZE, TILE_SIZE, TILE_SIZE)
                pygame.draw.rect(self.screen, color, rect)

                # Отрисовка шлюзов в городе
                if tile_info.get("is_gateway"):
                    # Теперь rect.center будет работать корректно
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

    def draw_status(self, world_manager, player_wx: int, player_wz: int):
        # ---> ИЗМЕНЕНИЕ ЗДЕСЬ <---
        # Вычисляем координаты чанка напрямую из мировых координат игрока.
        # Это самый надежный способ, который не зависит от имен атрибутов в WorldManager.
        current_cx = player_wx // CHUNK_SIZE
        current_cz = player_wz // CHUNK_SIZE

        status_text = (f"World: {world_manager.world_id} | "
                       f"Seed: {world_manager.current_seed} | "
                       f"Chunk: ({current_cx}, {current_cz}) | "
                       f"Player: ({player_wx}, {player_wz})")
        text_surface = self.font.render(status_text, True, (255, 255, 255))
        self.screen.blit(text_surface, (5, SCREEN_HEIGHT - 20))

    def draw_minimap(self, world_manager, player_cx: int, player_cz: int):
        """Новый метод для вызова отрисовки миникарты."""
        self.minimap.draw(world_manager, player_cx, player_cz)
