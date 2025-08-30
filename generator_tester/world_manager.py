# generator_tester/world_manager.py
import hashlib
import json
import pathlib
from typing import Dict, Tuple, Any, List

from engine.worldgen_core.base.preset import Preset
from engine.worldgen_core.world.world_generator import WorldGenerator
from engine.worldgen_core.base.export import write_chunk_rle_json, write_chunk_meta_json, write_preview_png
from generator_tester.config import PRESET_PATH, ARTIFACTS_ROOT, CHUNK_SIZE


class WorldManager:
    def __init__(self, city_seed: int):
        self.city_seed = city_seed
        self.preset = self._load_preset()
        self.generator = WorldGenerator(self.preset)
        self.cache: Dict[Tuple, Dict] = {}  # Кэш чанков в памяти

        # Текущее состояние
        self.world_id = "city"
        self.current_seed = city_seed
        self.cx = 0
        self.cz = 0

    def _load_preset(self) -> Preset:
        with open(PRESET_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return Preset.from_dict(data)

    def _get_chunk_path(self, world_id: str, seed: int, cx: int, cz: int) -> pathlib.Path:
        world_parts = world_id.split('/')
        return pathlib.Path(ARTIFACTS_ROOT, "world", *world_parts, str(seed), f"{cx}_{cz}")

    def _branch_seed(self, side: str) -> int:
        h = hashlib.blake2b(digest_size=8)
        h.update(str(self.city_seed).encode("utf-8"))
        h.update(b":")
        h.update(side.encode("utf-8"))
        return int.from_bytes(h.digest(), "little", signed=False)

    def get_chunk(self, cx: int, cz: int) -> Dict:
        """Главный метод: получает чанк из кэша, с диска или генерирует новый."""
        key = (self.world_id, self.current_seed, cx, cz)
        if key in self.cache:
            return self.cache[key]

        # Особый случай для центра города
        if self.world_id == "city" and cx == 0 and cz == 0:
            chunk_data = self._load_static_city()
            self.cache[key] = chunk_data
            return chunk_data

        chunk_path = self._get_chunk_path(self.world_id, self.current_seed, cx, cz)

        # Попытка загрузить с диска
        if (chunk_path / "chunk.rle.json").exists():
            with open(chunk_path / "chunk.rle.json", "r", encoding="utf-8") as f:
                chunk_data = json.load(f)
            self.cache[key] = chunk_data
            return chunk_data

        # Генерация нового чанка
        print(f"Генерация нового чанка: {key}")
        gen_params = {"seed": self.current_seed, "cx": cx, "cz": cz, "world_id": self.world_id}
        result = self.generator.generate(gen_params)

        # Сохранение на диск
        chunk_path.mkdir(parents=True, exist_ok=True)
        write_chunk_rle_json(str(chunk_path / "chunk.rle.json"), result.layers["kind"], result.size, result.seed, cx,
                             cz)
        # ... (можно добавить сохранение meta и preview) ...

        # Конвертируем для использования
        chunk_data = {"layers": result.layers, "ports": result.ports}
        self.cache[key] = chunk_data
        return chunk_data

    def move(self, dx: int, dz: int) -> bool:
        """Пытается переместиться в соседний чанк."""
        # Упрощенная логика перехода для тестера
        if self.world_id == "city" and self.cx == 0 and self.cz == 0 and dx == 1:  # Выход из города на восток
            self.world_id = "branch/E"
            self.current_seed = self._branch_seed("E")

        self.cx += dx
        self.cz += dz
        return True  # В тестере всегда разрешаем переход

    def get_current_chunk_data(self) -> Tuple[List[List[str]], List[List[float]]]:
        """Возвращает данные о текущем чанке (kind и height)."""
        data = self.get_chunk(self.cx, self.cz)

        # Раскодируем RLE, если нужно
        kind_payload = data.get("layers", {}).get("kind", {})
        if isinstance(kind_payload, dict):
            rows = kind_payload.get("rows", [])
            grid_ids = [val for r in rows for val, run in r for _ in range(run)]  # Упрощенное декодирование
            # Эта часть требует более надежного декодера
            # ВРЕМЕННАЯ ЗАГЛУШКА
            n = CHUNK_SIZE
            grid_names = [["ground"] * n for _ in range(n)]

        else:  # Если уже раскодировано
            grid_names = kind_payload

        height_grid = data.get("layers", {}).get("height_q", {}).get("grid", [])
        return grid_names, height_grid

    def _load_static_city(self) -> Dict:
        """Загружает статичный чанк города."""
        city_path = pathlib.Path(ARTIFACTS_ROOT, "world", "city", "static", "0_0", "chunk.rle.json")
        with open(city_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return {"layers": {"kind": data}}  # Упрощенная структура