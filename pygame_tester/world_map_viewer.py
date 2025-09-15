# pygame_tester/world_map_viewer.py
import pygame
import pathlib
import numpy as np
from collections import deque, OrderedDict
from typing import Dict, Tuple, Set, List

from .config import CHUNK_SIZE, BACKGROUND_COLOR
from game_engine_restructured.world.grid_utils import region_base

# --- Настройки стриминга ---
LOAD_BUDGET_PER_FRAME = 20
LOAD_RADIUS_CHUNKS = 5
UNLOAD_PADDING_CHUNKS = 1


class WorldMapViewer:
    """
    Стриминговый просмотрщик:
    - Кэширует только нужные тайлы.
    - Догружает видимые и окрестные тайлы малыми порциями.
    - Поддерживает и png-превью, и «сырые» слои (temperature/humidity) по запросу.
    """

    def __init__(
            self, artifacts_root: pathlib.Path, seed: int, min_cx: int = 0, min_cz: int = 0
    ):
        self.artifacts_root = artifacts_root
        self.seed = seed
        self.world_path = (
                self.artifacts_root / "world" / "world_location" / str(self.seed)
        )
        self.raw_path = self.artifacts_root / "world_raw" / str(self.seed)

        self.chunk_cache: "OrderedDict[tuple[int,int], pygame.Surface]" = OrderedDict()
        self.raw_layer_cache: "OrderedDict[tuple[int,int,str], pygame.Surface]" = (
            OrderedDict()
        )
        self.missing: set[tuple[int, int, str]] = set()

        self.min_cx = min_cx
        self.min_cz = min_cz
        self.max_cx = 0
        self.max_cz = 0

        self.preview_size = CHUNK_SIZE * 2
        self.active_layer = "preview"
        self._load_queue: deque[tuple[int, int, str]] = deque()
        self._enqueued: set[tuple[int, int, str]] = set()

    def _chunk_exists(self, cx: int, cz: int) -> bool:
        """Проверяет, существует ли preview.png для чанка."""
        p = self.world_path / f"{cx}_{cz}" / "preview.png"
        return p.exists()

    def _lru_put(self, cache: OrderedDict, key, value, capacity: int) -> None:
        cache[key] = value
        cache.move_to_end(key)
        while len(cache) > capacity:
            cache.popitem(last=False)

    def _lru_get(self, cache: OrderedDict, key):
        if key in cache:
            cache.move_to_end(key)
            return cache[key]
        return None

    def _get_chunk_image_now(self, cx: int, cz: int) -> pygame.Surface | None:
        key = (cx, cz)
        cached = self._lru_get(self.chunk_cache, key)
        if cached is not None:
            return cached

        preview_path = self.world_path / f"{cx}_{cz}" / "preview.png"
        if not preview_path.exists():
            return None
        try:
            image = pygame.image.load(str(preview_path)).convert()
        except pygame.error:
            return None

        self._lru_put(self.chunk_cache, key, image, self._cache_caps()[0])
        return image

    def _get_raw_layer_image_now(
            self, cx: int, cz: int, layer_name: str, world_manager
    ) -> pygame.Surface | None:
        key = (cx, cz, layer_name)
        cached = self._lru_get(self.raw_layer_cache, key)
        if cached is not None:
            return cached

        # --- НАЧАЛО ИСПРАВЛЕНИЯ ---
        # Исправлен вызов на существующий метод load_raw_regional_layer
        grid_data = world_manager.load_raw_regional_layer(cx, cz, layer_name)
        # --- КОНЕЦ ИСПРАВЛЕНИЯ ---

        if grid_data is None or grid_data.size == 0:
            return None

        min_val, max_val = 0.0, 1.0
        if layer_name == "temperature":
            temp_cfg = world_manager.preset.climate.get("temperature", {})
            min_val, max_val = temp_cfg.get("clamp_c", [-15.0, 35.0])
        elif layer_name == "humidity":
            hum_cfg = world_manager.preset.climate.get("humidity", {})
            min_val, max_val = hum_cfg.get("clamp", [0.0, 1.0])

        grid = np.clip(grid_data, min_val, max_val)
        norm = (grid - min_val) / (max_val - min_val + 1e-9)

        surf = pygame.Surface((CHUNK_SIZE, CHUNK_SIZE))
        if layer_name == "temperature":
            px = (norm * 255).astype(np.uint8)
            colors = np.zeros((CHUNK_SIZE, CHUNK_SIZE, 3), dtype=np.uint8)
            colors[:, :, 0] = px
            colors[:, :, 2] = 255 - px
            pygame.surfarray.blit_array(surf, colors)
        elif layer_name == "humidity":
            px = (norm * 255).astype(np.uint8)
            colors = np.zeros((CHUNK_SIZE, CHUNK_SIZE, 3), dtype=np.uint8)
            colors[:, :, 1] = px
            colors[:, :, 0] = px // 2
            pygame.surfarray.blit_array(surf, colors)

        self._lru_put(self.raw_layer_cache, key, surf, self._cache_caps()[1])
        return surf

    def _calc_visible_bounds(self, camera) -> Tuple[int, int, int, int]:
        rect = camera.get_visible_world_rect()
        start_cx = self.min_cx + int(rect.left // self.preview_size)
        end_cx = self.min_cx + int(rect.right // self.preview_size)
        start_cz = self.min_cz + int(rect.top // self.preview_size)
        end_cz = self.min_cz + int(rect.bottom // self.preview_size)
        return start_cx, end_cx, start_cz, end_cz

    def _cache_caps(self) -> Tuple[int, int]:
        side = LOAD_RADIUS_CHUNKS * 2 + 1 + (UNLOAD_PADDING_CHUNKS * 2)
        total_chunks = side * side
        return max(64, total_chunks), max(32, total_chunks // 2)

    def _enqueue_stream(self, world_manager, camera) -> None:
        center_wx = camera.x + (camera.viewport_width / (2 * camera.zoom))
        center_wy = camera.y + (camera.viewport_height / (2 * camera.zoom))
        center_cx, center_cz = self.world_pixel_to_chunk_coords(center_wx, center_wy)

        start_cx = center_cx - LOAD_RADIUS_CHUNKS
        end_cx = center_cx + LOAD_RADIUS_CHUNKS
        start_cz = center_cz - LOAD_RADIUS_CHUNKS
        end_cz = center_cz + LOAD_RADIUS_CHUNKS

        cand: List[Tuple[int, int]] = []
        for cz in range(start_cz, end_cz + 1):
            for cx in range(start_cx, end_cx + 1):
                cand.append((cx, cz))

        def priority(pair: Tuple[int, int]) -> float:
            dx = pair[0] - center_cx
            dz = pair[1] - center_cz
            return dx * dx + dz * dz

        cand.sort(key=priority)

        layer = self.active_layer
        for cx, cz in cand:
            key = (cx, cz, layer)
            if key in self._enqueued or key in self.missing:
                continue
            if layer == "preview" and not self._chunk_exists(cx, cz):
                self.missing.add(key)
                continue
            self._load_queue.append(key)
            self._enqueued.add(key)

    def _pump_stream(self, world_manager) -> None:
        budget = LOAD_BUDGET_PER_FRAME
        while budget > 0 and self._load_queue:
            cx, cz, layer = self._load_queue.popleft()
            self._enqueued.discard((cx, cz, layer))

            ok = True
            if layer == "preview":
                if self._get_chunk_image_now(cx, cz) is None:
                    ok = False
            else:
                if self._get_raw_layer_image_now(cx, cz, layer, world_manager) is None:
                    ok = False
            if not ok:
                self.missing.add((cx, cz, layer))

    def draw(self, target_surface: pygame.Surface, camera, world_manager):
        self._enqueue_stream(world_manager, camera)
        self._pump_stream(world_manager)

        if self._load_queue:
            pygame.display.set_caption(
                f"stream queued: {len(self._load_queue)} | cache png={len(self.chunk_cache)} raw={len(self.raw_layer_cache)}"
            )
        target_surface.fill(BACKGROUND_COLOR)

        start_cx_draw, end_cx_draw, start_cz_draw, end_cz_draw = (
            self._calc_visible_bounds(camera)
        )
        layer = self.active_layer

        for cz in range(start_cz_draw, end_cz_draw + 1):
            for cx in range(start_cx_draw, end_cx_draw + 1):
                image = None
                if layer == "preview":
                    image = self._lru_get(self.chunk_cache, (cx, cz))
                else:
                    image = self._lru_get(self.raw_layer_cache, (cx, cz, layer))

                world_x = (cx - self.min_cx) * self.preview_size
                world_y = (cz - self.min_cz) * self.preview_size
                screen_x, screen_y = camera.world_to_screen(world_x, world_y)
                scaled = int(self.preview_size * camera.zoom)

                if image and scaled > 1:
                    if image.get_width() != scaled:
                        image = pygame.transform.scale(image, (scaled, scaled))
                    target_surface.blit(image, (screen_x, screen_y))
                elif scaled > 1:
                    placeholder = pygame.Surface((scaled, scaled))
                    placeholder.fill((28, 30, 36))
                    pygame.draw.rect(
                        placeholder, (60, 60, 70), placeholder.get_rect(), 1
                    )
                    target_surface.blit(placeholder, (screen_x, screen_y))

        center_wx = camera.x + camera.viewport_width / 2.0
        center_wy = camera.y + camera.viewport_height / 2.0
        center_cx, center_cz = self.world_pixel_to_chunk_coords(center_wx, center_wy)

        keep_radius = LOAD_RADIUS_CHUNKS + UNLOAD_PADDING_CHUNKS
        start_cx_keep = center_cx - keep_radius
        end_cx_keep = center_cx + keep_radius
        start_cz_keep = center_cz - keep_radius
        end_cz_keep = center_cz + keep_radius

        chunks_to_keep = set(
            (cx, cz)
            for cz in range(start_cz_keep, end_cz_keep + 1)
            for cx in range(start_cx_keep, end_cx_keep + 1)
        )

        for key in list(self.chunk_cache.keys()):
            if key not in chunks_to_keep:
                self.chunk_cache.pop(key, None)
        for key in list(self.raw_layer_cache.keys()):
            if (key[0], key[1]) not in chunks_to_keep:
                self.raw_layer_cache.pop(key, None)

    def world_pixel_to_chunk_coords(self, wx: float, wy: float) -> Tuple[int, int]:
        cx = self.min_cx + int(wx // self.preview_size)
        cz = self.min_cz + int(wy // self.preview_size)
        return cx, cz

    def get_available_layers(self) -> list[str]:
        return ["preview", "temperature", "humidity"]

    def set_active_layer(self, layer_name: str):
        self.active_layer = layer_name
        self._load_queue.clear()
        self._enqueued.clear()
        self.missing.clear()
        print(f"[WorldMap] Switched to layer: {layer_name}")