# pygame_tester/world_map_viewer.py
import pygame
import pathlib
from typing import Dict, Tuple, Set

from pygame_tester.config import CHUNK_SIZE, BACKGROUND_COLOR


class WorldMapViewer:
    def __init__(self, artifacts_root: pathlib.Path, seed: int):
        self.artifacts_root = artifacts_root
        self.seed = seed
        self.world_path = self.artifacts_root / "world" / "world_location" / str(self.seed)

        # --- ИЗМЕНЕНИЕ: Вместо загрузки используем кэш и список путей ---
        self.chunk_cache: Dict[Tuple[int, int], pygame.Surface] = {}
        self.existing_chunk_coords: Set[Tuple[int, int]] = set()
        self.preview_size = CHUNK_SIZE * 2  # Предосмотры у нас 2x размера чанка

        self.min_cx, self.min_cz = 0, 0
        self.max_cx, self.max_cz = 0, 0

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
                # В случае ошибки загрузки, запоминаем, что чанк "битый"
                self.existing_chunk_coords.remove((cx, cz))
                return None
        return None

    def draw(self, target_surface: pygame.Surface, camera):
        """Главная функция отрисовки со стримингом."""
        target_surface.fill(BACKGROUND_COLOR)

        # 1. Определяем, какие чанки видимы камере
        visible_world_rect = camera.get_visible_world_rect()

        start_cx = self.min_cx + int(visible_world_rect.left // self.preview_size)
        end_cx = self.min_cx + int(visible_world_rect.right // self.preview_size)
        start_cz = self.min_cz + int(visible_world_rect.top // self.preview_size)
        end_cz = self.min_cz + int(visible_world_rect.bottom // self.preview_size)

        # 2. Отрисовываем только видимые чанки
        for cz in range(start_cz, end_cz + 1):
            for cx in range(start_cx, end_cx + 1):
                image = self._get_chunk_image(cx, cz)
                if image:
                    # Рассчитываем позицию чанка в мировых пиксельных координатах
                    world_x = (cx - self.min_cx) * self.preview_size
                    world_y = (cz - self.min_cz) * self.preview_size

                    # Преобразуем мировые координаты в экранные
                    screen_x, screen_y = camera.world_to_screen(world_x, world_y)

                    # Масштабируем и отрисовываем
                    scaled_size = int(self.preview_size * camera.zoom)
                    if scaled_size > 1:
                        scaled_image = pygame.transform.scale(image, (scaled_size, scaled_size))
                        target_surface.blit(scaled_image, (screen_x, screen_y))

        # 3. Очищаем кэш от невидимых чанков (простая стратегия)
        visible_coords = set((cx, cz) for cz in range(start_cz, end_cz + 2) for cx in range(start_cx, end_cx + 2))
        cached_coords = list(self.chunk_cache.keys())
        for coords in cached_coords:
            if coords not in visible_coords:
                del self.chunk_cache[coords]

    def world_pixel_to_chunk_coords(self, wx: float, wy: float) -> Tuple[int, int]:
        cx = self.min_cx + int(wx // self.preview_size)
        cz = self.min_cz + int(wy // self.preview_size)
        return cx, cz

    # (остальные методы без изменений)
    def get_available_layers(self) -> list[str]:
        return ["preview"]

    def set_active_layer(self, layer_name: str):
        self.active_layer = layer_name
        print(f"[WorldMap] Switched to layer: {layer_name}")