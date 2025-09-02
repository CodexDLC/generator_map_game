# pygame_tester/world_manager.py
import json
import pathlib
import time
from typing import Dict, Tuple

# --- ИЗМЕНЕНИЯ: Все импорты теперь ведут в game_engine ---
from game_engine.core.preset import Preset
from game_engine.generators.world.world_generator import WorldGenerator
from game_engine.core.export import write_preview_png, write_chunk_rle_json, write_chunk_meta_json
from game_engine.core.utils.rle import decode_rle_rows
from game_engine.core.constants import ID_TO_KIND, DEFAULT_PALETTE
from game_engine.game_logic.transition_manager import WorldTransitionManager
from game_engine.world_structure.regions import RegionManager

from .config import PRESET_PATH, ARTIFACTS_ROOT


class WorldManager:
    def __init__(self, city_seed: int):
        self.city_seed = city_seed
        self.preset = self._load_preset()

        # --- НАЧАЛО ИЗМЕНЕНИЙ ---
        # 1. Создаем RegionManager с сидом мира
        self.region_manager = RegionManager(world_seed=city_seed)
        # 2. Передаем preset И region_manager в конструктор WorldGenerator
        self.generator = WorldGenerator(self.preset, self.region_manager)
        # --- КОНЕЦ ИЗМЕНЕНИЙ ---

        self.cache: Dict[Tuple, Dict | None] = {}
        self.preload_radius = 1

        self.world_id = "city"
        self.current_seed = city_seed

        self.player_chunk_cx = 0
        self.player_chunk_cz = 0

        self.transition_manager = WorldTransitionManager(self)


    def get_chunk_data(self, cx: int, cz: int) -> Dict | None:
        """
        Универсальный метод загрузки данных чанка.
        Кэширует только успешные загрузки, чтобы избежать проблем с многопроцессностью.
        """
        print(f"\n[Loader] Requesting chunk ({self.world_id}, seed={self.current_seed}, pos=({cx},{cz}))...")

        key = (self.world_id, self.current_seed, cx, cz)
        if key in self.cache:
            # В кэше лежит только успешно загруженный чанк
            print(f"[Loader] -> Found in cache.")
            return self.cache[key]

        chunk_path = self._get_chunk_path(self.world_id, self.current_seed, cx, cz)
        rle_path = chunk_path / "chunk.rle.json"

        print(f"[Loader] -> Checking file at: {rle_path}")

        if not rle_path.exists():
            print(f"[Loader] -> File does not exist.")
            # --- ИЗМЕНЕНИЕ: БОЛЬШЕ НЕ КЭШИРУЕМ None ---
            return None

        try:
            print(f"[Loader] -> File found. Attempting to load and decode...")
            with open(rle_path, "r", encoding="utf-8") as f:
                doc = json.load(f)

            layers = doc.get("layers")
            if layers:
                kind_payload = layers.get("kind", {})
                height_payload = layers.get("height_q", {})
            else:
                kind_payload = doc
                height_payload = {}

            decoded_rows = decode_rle_rows(kind_payload.get("rows", []))

            kind_grid = []
            for row in decoded_rows:
                new_row = []
                for tile_value in row:
                    if isinstance(tile_value, str):
                        new_row.append(tile_value)
                    else:
                        new_row.append(ID_TO_KIND.get(int(tile_value), "void"))
                kind_grid.append(new_row)

            height_grid_rows = height_payload.get("rows", [])
            height_grid = decode_rle_rows(height_grid_rows)

            if kind_grid and not height_grid:
                height_grid = [[0.0] * len(kind_grid[0]) for _ in range(len(kind_grid))]

            decoded = {"kind": kind_grid, "height": height_grid}
            # --- ИЗМЕНЕНИЕ: КЭШИРУЕМ ТОЛЬКО УСПЕШНЫЙ РЕЗУЛЬТАТ ---
            self.cache[key] = decoded
            print(f"[Loader] -> Success! Chunk loaded and cached.")
            return decoded
        except Exception as e:
            print(f"!!! [Loader] CRITICAL ERROR: Failed to load or decode chunk. Error: {e}")
            return None

    def _load_preset(self) -> Preset:
        with open(PRESET_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return Preset.from_dict(data)

    def _get_chunk_path(self, world_id: str, seed: int, cx: int, cz: int) -> pathlib.Path:
        # <<< НАЧАЛО ПРЕДЛАГАЕМОГО ИЗМЕНЕНИЯ >>>

        # Если мир - это "city", мы используем жестко заданный путь к статике,
        # полностью игнорируя переданный seed.
        if world_id == "city":
            return ARTIFACTS_ROOT / "world" / "city" / "static" / f"{cx}_{cz}"

        # Для всех остальных миров (world_location, dungeon и т.д.)
        # используется стандартный процедурный путь с сидом.
        else:
            return ARTIFACTS_ROOT / "world" / world_id / str(seed) / f"{cx}_{cz}"

    def get_chunks_for_preloading(self, center_cx: int, center_cz: int) -> list:
        tasks = []
        for dz in range(-self.preload_radius, self.preload_radius + 1):
            for dx in range(-self.preload_radius, self.preload_radius + 1):
                cx, cz = center_cx + dx, center_cz + dz

                chunk_path = self._get_chunk_path(self.world_id, self.current_seed, cx, cz)
                if not (chunk_path / "chunk.rle.json").exists():
                    tasks.append((self.world_id, self.current_seed, cx, cz))
        return tasks

    def _load_or_generate_chunk(self, cx: int, cz: int):
        # Этот метод вызывается воркером. Он теперь не содержит особой логики для города.
        chunk_path = self._get_chunk_path(self.world_id, self.current_seed, cx, cz)
        if (chunk_path / "chunk.rle.json").exists():
            return

        t_total_start = time.perf_counter()

        # Передаем world_id в генератор, чтобы он мог применять особые правила
        gen_params = {"seed": self.current_seed, "cx": cx, "cz": cz, "world_id": self.world_id}
        result = self.generator.generate(gen_params)

        t_export_start = time.perf_counter()
        meta_path = str(chunk_path / "chunk.meta.json")
        rle_path = str(chunk_path / "chunk.rle.json")
        preview_path = str(chunk_path / "preview.png")

        write_chunk_rle_json(rle_path, result.layers, result.size, result.seed, cx, cz)

        palette = dict(DEFAULT_PALETTE)
        palette.update(self.preset.export.get("palette", {}))
        write_preview_png(preview_path, result.layers["kind"], palette, result.ports)

        export_duration = (time.perf_counter() - t_export_start) * 1000
        total_duration = (time.perf_counter() - t_total_start) * 1000

        timings = result.metrics.get("gen_timings_ms", {})
        timings["export"] = export_duration
        timings["total"] = total_duration
        result.metrics["gen_timings_ms"] = timings

        meta_data = {
            "version": "1.0", "type": "chunk_meta", "seed": result.seed, "size": result.size,
            "cx": cx, "cz": cz, "world_id": self.world_id,
            "edges": result.metrics.get("edges", {}), "ports": result.ports,
            "metrics": result.metrics
        }
        write_chunk_meta_json(meta_path, meta_data)

        print(
            f"--- Generation Timings for chunk {(self.world_id, self.current_seed, cx, cz)} ---\n"
            f"  - Total          : {timings.get('total', 0):8.2f} ms"
        )