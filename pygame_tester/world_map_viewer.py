# pygame_tester/world_map_viewer.py
import pygame
import pathlib
import numpy as np
from typing import Dict, Tuple, Set

from .config import CHUNK_SIZE, BACKGROUND_COLOR
from game_engine_restructured.world.grid_utils import region_base


class WorldMapViewer:
    def __init__(self, artifacts_root: pathlib.Path, seed: int):
        self.artifacts_root = artifacts_root
        self.seed = seed
        self.world_path = self.artifacts_root / "world" / "world_location" / str(self.seed)
        self.raw_path = self.artifacts_root / "world_raw" / str(self.seed)

        self.chunk_cache: Dict[Tuple[int, int], pygame.Surface] = {}
        self.raw_layer_cache: Dict[Tuple[int, int, str], pygame.Surface] = {}
        self.existing_chunk_coords: Set[Tuple[int, int]] = set()

        self.min_cx, self.min_cz = 0, 0
        self.max_cx, self.max_cz = 0, 0
        self.preview_size = CHUNK_SIZE * 2
        self.active_layer = "preview"

        self._discover_chunks()

    def _discover_chunks(self):
        """Находит все доступные чанки, но не загружает их."""
        print("[WorldMap] Discovering available chunks...")
        if not self.world_path.exists():
            return

        chunk_coords = []
        for chunk_dir in self.world_path.iterdir():
            if chunk_dir.is_dir() and (chunk_dir / "preview.png").exists():
                try:
                    cx, cz = map(int, chunk_dir.name.split('_'))
                    self.existing_chunk_coords.add((cx, cz))
                    chunk_coords.append((cx, cz))
                except ValueError:
                    continue

        if not chunk_coords:
            return

        self.min_cx = min(c[0] for c in chunk_coords)
        self.min_cz = min(c[1] for c in chunk_coords)
        self.max_cx = max(c[0] for c in chunk_coords)
        self.max_cz = max(c[1] for c in chunk_coords)
        print(f"[WorldMap] -> Found {len(self.existing_chunk_coords)} chunks.")

    def _get_chunk_image(self, cx: int, cz: int) -> pygame.Surface | None:
        """Получает изображение чанка из кэша или загружает его с диска."""
        if (cx, cz) in self.chunk_cache:
            return self.chunk_cache[(cx, cz)]

        if (cx, cz) in self.existing_chunk_coords:
            preview_path = self.world_path / f"{cx}_{cz}" / "preview.png"
            try:
                image = pygame.image.load(str(preview_path)).convert()
                self.chunk_cache[(cx, cz)] = image
                return image
            except pygame.error:
                self.existing_chunk_coords.remove((cx, cz))
                return None
        return None

    def _get_raw_layer_image(self, cx: int, cz: int, layer_name: str, world_manager) -> pygame.Surface | None:
        """Получает изображение отладочного слоя из кэша или генерирует его."""
        cache_key = (cx, cz, layer_name)
        if cache_key in self.raw_layer_cache:
            return self.raw_layer_cache[cache_key]

        data = world_manager.load_raw_json(cx, cz, layer_name)
        if data is None or not data:
            return None

        # Конвертируем список списков в numpy массив для удобства
        grid_data = np.array(data)

        # Нормализуем данные
        min_val = np.min(grid_data)
        max_val = np.max(grid_data)
        if max_val - min_val == 0:
            norm_data = np.zeros_like(grid_data)
        else:
            norm_data = (grid_data - min_val) / (max_val - min_val)

        # Создаем поверхность и раскрашиваем
        surface = pygame.Surface((CHUNK_SIZE, CHUNK_SIZE))
        if layer_name == "temperature":
            # От синего (холод) до красного (тепло)
            pixels = (np.interp(norm_data, [0, 1], [0, 255])).astype(int)
            colors = np.zeros((CHUNK_SIZE, CHUNK_SIZE, 3), dtype=np.uint8)
            colors[:, :, 0] = pixels  # Красный канал
            colors[:, :, 2] = 255 - pixels  # Синий канал
            pygame.surfarray.blit_array(surface, colors)
        elif layer_name == "humidity":
            # От коричневого (сухо) до зеленого (влажно)
            pixels = (np.interp(norm_data, [0, 1], [0, 255])).astype(int)
            colors = np.zeros((CHUNK_SIZE, CHUNK_SIZE, 3), dtype=np.uint8)
            colors[:, :, 0] = pixels // 2  # Коричневый
            colors[:, :, 1] = pixels  # Зеленый канал
            pygame.surfarray.blit_array(surface, colors)
        else:
            return None

        self.raw_layer_cache[cache_key] = surface
        return surface

    def draw(self, target_surface: pygame.Surface, camera, world_manager):
        """Главная функция отрисовки со стримингом."""
        target_surface.fill(BACKGROUND_COLOR)

        visible_world_rect = camera.get_visible_world_rect()

        # Рассчитываем видимые чанки (упрощено для демонстрации)
        start_cx = self.min_cx + int(visible_world_rect.left // self.preview_size)
        end_cx = self.min_cx + int(visible_world_rect.right // self.preview_size)
        start_cz = self.min_cz + int(visible_world_rect.top // self.preview_size)
        end_cz = self.min_cz + int(visible_world_rect.bottom // self.preview_size)

        # Отрисовываем чанки
        for cz in range(start_cz, end_cz + 1):
            for cx in range(start_cx, end_cx + 1):
                image = None
                if self.active_layer == "preview":
                    image = self._get_chunk_image(cx, cz)
                else:
                    image = self._get_raw_layer_image(cx, cz, self.active_layer, world_manager)

                if image:
                    world_x = (cx - self.min_cx) * self.preview_size
                    world_y = (cz - self.min_cz) * self.preview_size

                    screen_x, screen_y = camera.world_to_screen(world_x, world_y)
                    scaled_size = int(self.preview_size * camera.zoom)

                    if scaled_size > 1:
                        scaled_image = pygame.transform.scale(image, (scaled_size, scaled_size))
                        target_surface.blit(scaled_image, (screen_x, screen_y))

        # Очищаем кэш от невидимых чанков
        visible_coords = set((cx, cz) for cz in range(start_cz, end_cz + 2) for cx in range(start_cx, end_cx + 2))
        cached_coords = list(self.chunk_cache.keys())
        for coords in cached_coords:
            if coords not in visible_coords:
                del self.chunk_cache[coords]

        cached_raw_coords = list(self.raw_layer_cache.keys())
        for coords in cached_raw_coords:
            if (coords[0], coords[1]) not in visible_coords:
                del self.raw_layer_cache[coords]

    def world_pixel_to_chunk_coords(self, wx: float, wy: float) -> Tuple[int, int]:
        cx = self.min_cx + int(wx // self.preview_size)
        cz = self.min_cz + int(wy // self.preview_size)
        return cx, cz

    def get_available_layers(self) -> list[str]:
        return ["preview", "temperature", "humidity"]

    def set_active_layer(self, layer_name: str):
        self.active_layer = layer_name
        print(f"[WorldMap] Switched to layer: {layer_name}")