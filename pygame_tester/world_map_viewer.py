# pygame_tester/world_map_viewer.py
import pygame
import pathlib
import numpy as np
from collections import deque, OrderedDict
from typing import Dict, Tuple, Set, List

from .config import CHUNK_SIZE, BACKGROUND_COLOR
from game_engine_restructured.world.grid_utils import region_base


# --- Настройки стриминга ---
LOAD_BUDGET_PER_FRAME = 10   # Сколько тайлов максимум грузим за один кадр (I/O на диск)
KEEP_EXTRA_RINGS = 1         # Сколько «колец» вокруг видимой области оставляем в кэше
REGION_RING_PRELOAD = 1      # Сколько соседних регионов (кольцами) предзагружаем вокруг центрального

class WorldMapViewer:
    """
    Стриминговый просмотрщик:
    - Кэширует только нужные тайлы.
    - Догружает видимые и окрестные тайлы малыми порциями.
    - Поддерживает и png-превью, и «сырые» слои (temperature/humidity) по запросу.
    """

    def __init__(self, artifacts_root: pathlib.Path, seed: int):
        self.artifacts_root = artifacts_root
        self.seed = seed
        self.world_path = self.artifacts_root / "world" / "world_location" / str(self.seed)
        self.raw_path = self.artifacts_root / "world_raw" / str(self.seed)

        # Кэши делаем LRU, чтобы можно было выкидывать старьё.
        self.chunk_cache: "OrderedDict[tuple[int,int], pygame.Surface]" = OrderedDict()
        self.raw_layer_cache: "OrderedDict[tuple[int,int,str], pygame.Surface]" = OrderedDict()
        self.missing: set[tuple[int, int, str]] = set()
        # Базовые смещения «сетки чанков» (если нет манифеста)
        self.min_cx = 0
        self.min_cz = 0
        self.max_cx = 0
        self.max_cz = 0

        self.preview_size = CHUNK_SIZE * 2
        self.active_layer = "preview"
        self._load_queue: deque[tuple[int, int, str]] = deque()
        self._enqueued: set[tuple[int, int, str]] = set()

    # ------------------------------------------------------------------
    # ИНДЕКСАЦИЯ ФАЙЛОВ/ДИРЕКТОРИЙ
    # ------------------------------------------------------------------



    def _chunk_exists(self, cx: int, cz: int) -> bool:
        p = self.world_path / f"{cx}_{cz}" / "preview.png"
        return p.exists()

    # ------------------------------------------------------------------
    # ЗАГРУЗКА ТАЙЛОВ (PNG/RAW) С КЭШЕМ
    # ------------------------------------------------------------------

    def _lru_put(self, cache: OrderedDict, key, value, capacity: int) -> None:
        """
        Кладём в LRU-кэш. Если переполнен — выкидываем старейший элемент.
        """
        cache[key] = value
        cache.move_to_end(key)
        while len(cache) > capacity:
            cache.popitem(last=False)

    def _lru_get(self, cache: OrderedDict, key):
        """
        Получаем из LRU-кэша, если есть — помечаем «хит» (переносим в конец).
        """
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

    def _get_raw_layer_image_now(self, cx: int, cz: int, layer_name: str, world_manager) -> pygame.Surface | None:
        """
        Мгновенная генерация изображения для «сырого» слоя (temperature/humidity)
        из JSON-а региона, с вырезанием нужного куска. Только для стримера.
        """
        key = (cx, cz, layer_name)
        cached = self._lru_get(self.raw_layer_cache, key)
        if cached is not None:
            return cached

        grid_data = world_manager.load_raw_json(cx, cz, layer_name)
        if grid_data is None or grid_data.size == 0:
            return None

        # Нормализация по глобальным клампам из пресета
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

    # ------------------------------------------------------------------
    # СТРимЕР: планирование и порционная загрузка
    # ------------------------------------------------------------------

    def _calc_visible_bounds(self, camera) -> Tuple[int, int, int, int]:
        """
        В каком прямоугольнике (в координатах чанков) камера реально что-то видит?
        """
        rect = camera.get_visible_world_rect()
        start_cx = self.min_cx + int(rect.left // self.preview_size)
        end_cx   = self.min_cx + int(rect.right // self.preview_size)
        start_cz = self.min_cz + int(rect.top // self.preview_size)
        end_cz   = self.min_cz + int(rect.bottom // self.preview_size)
        return start_cx, end_cx, start_cz, end_cz

    def _cache_caps(self) -> Tuple[int, int]:
        """
        Вместимость LRU-кэшей для PNG и RAW, исходя из видимой области.
        Немного запасаемся (кольцами), чтобы не перезагружать туда-сюда.
        """
        # Простейшая оценка: видим NхM тайлов, +припуск колец
        # 4 * (N+2r)*(M+2r) — PNG; RAW обычно тяжелее: оставим поменьше.
        # Размеры оценим как 8x8 на типичном зуме.
        n = m = 12  # безопасный верхний предел для разных зумов
        rings = KEEP_EXTRA_RINGS + 1
        png_cap = max(64, (n + 2 * rings) * (m + 2 * rings))
        raw_cap = max(32, (n + 2 * rings) * (m + 2 * rings) // 2)
        return png_cap, raw_cap

    def _enqueue_stream(self, world_manager, camera) -> None:
        """
        Планируем, что грузить в первую очередь:
        1) Вся видимая область (активный слой).
        2) Кольца вокруг неё.
        3) Приоритет — по расстоянию от центра камеры.
        4) Сначала регион, где центр камеры, затем соседние регионы кольцами.
        """
        start_cx, end_cx, start_cz, end_cz = self._calc_visible_bounds(camera)
        center_wx = camera.x + camera.width  / 2
        center_wy = camera.y + camera.height / 2

        # Центр в координатах чанков
        center_cx = self.min_cx + int(center_wx // self.preview_size)
        center_cz = self.min_cz + int(center_wy // self.preview_size)

        # Размер региона из пресета
        region_size = world_manager.preset.region_size

        # Базовый чанк региона, где сейчас центр камеры
        base_rx, base_rz = region_base(center_cx, center_cz, region_size)

        def region_of(cx: int, cz: int) -> Tuple[int, int]:
            brx, brz = region_base(cx, cz, region_size)
            return (brx // region_size, brz // region_size)

        # Соберём список кандидатов (видимая область + припуск колец)
        pad = KEEP_EXTRA_RINGS
        cand: List[Tuple[int, int]] = []
        for cz in range(start_cz - pad, end_cz + 1 + pad):
            for cx in range(start_cx - pad, end_cx + 1 + pad):
                cand.append((cx, cz))

        # Сортируем по двум ключам:
        # (A) «кольца регионов» от центрального региона,
        # (B) расстояние от центра экрана (чтобы центр грузился первым).
        crx, crz = (base_rx // region_size, base_rz // region_size)
        def priority(pair: Tuple[int, int]) -> Tuple[int, float]:
            rcx, rcz = region_of(pair[0], pair[1])
            ring = abs(rcx - crx) + abs(rcz - crz)  # манхэттен по индексам регионов
            dx = pair[0] - center_cx
            dz = pair[1] - center_cz
            return (ring, dx*dx + dz*dz)

        cand.sort(key=priority)

        layer = self.active_layer
        for (cx, cz) in cand:
            key = (cx, cz, layer)
            if key in self._enqueued or key in self.missing:
                continue
            if layer == "preview" and not self._chunk_exists(cx, cz):
                self.missing.add(key)
                continue
            self._load_queue.append(key)
            self._enqueued.add(key)

    def _pump_stream(self, world_manager) -> None:
        """
        Выгребаем из очереди не более LOAD_BUDGET_PER_FRAME записей
        и реально грузим тайлы (PNG или RAW).
        """
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

    # ------------------------------------------------------------------
    # РЕНДЕР
    # ------------------------------------------------------------------

    def draw(self, target_surface: pygame.Surface, camera, world_manager):
        """
        Главная функция отрисовки:
        - планируем загрузку,
        - подгружаем партиями,
        - рисуем (если тайл ещё не в кэше — рисуем плейсхолдер).
        """
        loaded = len(self._load_queue)

        # после отрисовки


        # 1) Планируем что надо (видимая область -> очередь)
        self._enqueue_stream(world_manager, camera)
        # 2) Пытаемся подгрузить немного (I/O бюджет на кадр)
        self._pump_stream(world_manager)

        if loaded:
            pygame.display.set_caption(
                f"stream queued: {loaded} | cache png={len(self.chunk_cache)} raw={len(self.raw_layer_cache)}")
        target_surface.fill(BACKGROUND_COLOR)

        start_cx, end_cx, start_cz, end_cz = self._calc_visible_bounds(camera)
        layer = self.active_layer

        for cz in range(start_cz, end_cz + 1):
            for cx in range(start_cx, end_cx + 1):
                # Пытаемся достать из кэша. НИЧЕГО НЕ ГРУЗИМ СЕЙЧАС, ТОЛЬКО ЧИТАЕМ.
                image = None
                if layer == "preview":
                    image = self._lru_get(self.chunk_cache, (cx, cz))
                else:
                    image = self._lru_get(self.raw_layer_cache, (cx, cz, layer))

                # Где рисовать на экране?
                world_x = (cx - self.min_cx) * self.preview_size
                world_y = (cz - self.min_cz) * self.preview_size
                screen_x, screen_y = camera.world_to_screen(world_x, world_y)
                scaled = int(self.preview_size * camera.zoom)

                # Если тайл уже есть — рисуем
                if image and scaled > 1:
                    if image.get_width() != scaled:
                        image = pygame.transform.scale(image, (scaled, scaled))
                    target_surface.blit(image, (screen_x, screen_y))
                else:
                    # Иначе — плейсхолдер (серый прямоугольник с сеткой)
                    if scaled > 1:
                        placeholder = pygame.Surface((scaled, scaled))
                        placeholder.fill((28, 30, 36))
                        pygame.draw.rect(placeholder, (60, 60, 70), placeholder.get_rect(), 1)
                        target_surface.blit(placeholder, (screen_x, screen_y))

        # LRU-кэш автоматически ограничивается _cache_caps(),
        # но дополнительно удалим сырые тайлы, которые точно вне зоны интереса
        # (видимая + одно кольцо).
        visible = set((cx, cz) for cz in range(start_cz-KEEP_EXTRA_RINGS, end_cz+1+KEEP_EXTRA_RINGS)
                                for cx in range(start_cx-KEEP_EXTRA_RINGS, end_cx+1+KEEP_EXTRA_RINGS))
        for key in list(self.chunk_cache.keys()):
            if key not in visible:
                self.chunk_cache.pop(key, None)
        for key in list(self.raw_layer_cache.keys()):
            if (key[0], key[1]) not in visible:
                self.raw_layer_cache.pop(key, None)

    # ------------------------------------------------------------------
    # СЛОИ/СЕРВИС
    # ------------------------------------------------------------------

    def world_pixel_to_chunk_coords(self, wx: float, wy: float) -> Tuple[int, int]:
        cx = self.min_cx + int(wx // self.preview_size)
        cz = self.min_cz + int(wy // self.preview_size)
        return cx, cz

    def get_available_layers(self) -> list[str]:
        return ["preview", "temperature", "humidity"]

    def set_active_layer(self, layer_name: str):
        self.active_layer = layer_name
        # При смене слоя очередь надо очистить и пересчитать приоритеты
        self._load_queue.clear()
        self._enqueued.clear()
        print(f"[WorldMap] Switched to layer: {layer_name}")

    def _chunk_exists(self, cx, cz):
        pass
