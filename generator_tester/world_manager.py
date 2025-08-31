import hashlib
import json
import pathlib
import time
from typing import Dict, Tuple, Any

from engine.worldgen_core.base.preset import Preset
from engine.worldgen_core.world.world_generator import WorldGenerator
from engine.worldgen_core.base.export import write_preview_png, write_chunk_rle_json, write_chunk_meta_json
from engine.worldgen_core.utils.rle import decode_rle_rows
from engine.worldgen_core.base.constants import ID_TO_KIND, KIND_GROUND
from .config import CHUNK_SIZE, PRESET_PATH, ARTIFACTS_ROOT


class WorldManager:
    def __init__(self, city_seed: int):
        self.city_seed = city_seed
        self.preset = self._load_preset()
        self.generator = WorldGenerator(self.preset)
        self.cache: Dict[Tuple, Dict | None] = {}
        self.preload_radius = 1

        self.world_id = "city"
        self.current_seed = city_seed
        self.player_chunk_cx = 0
        self.player_chunk_cz = 0

    def _load_preset(self) -> Preset:
        with open(PRESET_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return Preset.from_dict(data)

    def _get_chunk_path(self, world_id: str, seed: int, cx: int, cz: int) -> pathlib.Path:
        world_parts = world_id.split('/')
        return ARTIFACTS_ROOT / "world" / pathlib.Path(*world_parts) / str(seed) / f"{cx}_{cz}"

    def _branch_seed(self, side: str) -> int:
        h = hashlib.blake2b(digest_size=8)
        h.update(str(self.city_seed).encode("utf-8"))
        h.update(b":")
        h.update(side.encode("utf-8"))
        return int.from_bytes(h.digest(), "little", signed=False)

    def _branch_domain(self, bid: str) -> dict:
        branches_cfg = self.preset.to_dict().get("branches", {})
        return dict(branches_cfg.get(bid, {}).get("domain", {}))

    @staticmethod
    def _in_domain(cx: int, cz: int, dom: dict) -> bool:
        if "x_min" in dom and cx < int(dom["x_min"]): return False
        if "x_max" in dom and cx > int(dom["x_max"]): return False
        if "z_min" in dom and cz < int(dom["z_min"]): return False
        if "z_max" in dom and cz > int(dom["z_max"]): return False
        return True

    def get_chunk_data(self, cx: int, cz: int) -> Dict | None:
        key = (self.world_id, self.current_seed, cx, cz)
        if key in self.cache:
            return self.cache[key]

        # Определяем путь к файлу
        if self.world_id == "city" and cx == 0 and cz == 0:
            rle_path = ARTIFACTS_ROOT / "world" / "city" / "static" / "0_0" / "chunk.rle.json"
        else:
            chunk_path = self._get_chunk_path(self.world_id, self.current_seed, cx, cz)
            rle_path = chunk_path / "chunk.rle.json"

        # --- ИСПРАВЛЕНИЕ ЛОГИКИ КЭШИРОВАНИЯ ---
        # Если файла нет, просто возвращаем None, НЕ КЭШИРУЯ результат
        if not rle_path.exists():
            return None

        # Если файл есть, загружаем, обрабатываем и ТОЛЬКО ТОГДА кэшируем
        try:
            with open(rle_path, "r", encoding="utf-8") as f:
                rle_data = json.load(f)

            raw_data = {"layers": {"kind": rle_data}}
            kind_payload = raw_data.get("layers", {}).get("kind", {})

            grid_ids = decode_rle_rows(kind_payload.get("rows", []))
            kind_grid = [[ID_TO_KIND.get(v, "ground") for v in row] for row in grid_ids]

            height_grid = []  # Высоты пока не загружаем для простоты

            decoded_chunk = {"kind": kind_grid, "height": height_grid}
            self.cache[key] = decoded_chunk  # <-- Кэшируем только УСПЕШНЫЙ результат
            return decoded_chunk
        except json.JSONDecodeError:
            print(f"Warning: Could not decode JSON for chunk at {cx}, {cz}. File might be incomplete.")
            return None  # Не кэшируем, если файл битый или недописан

    def get_chunks_for_preloading(self, center_cx: int, center_cz: int) -> list:
        tasks = []
        domain = {}
        is_branch = self.world_id.startswith("branch/")
        if is_branch:
            branch_id = self.world_id.split('/', 1)[1]
            domain = self._branch_domain(branch_id)

        for dz in range(-self.preload_radius, self.preload_radius + 1):
            for dx in range(-self.preload_radius, self.preload_radius + 1):
                cx, cz = center_cx + dx, center_cz + dz
                if is_branch and not self._in_domain(cx, cz, domain):
                    continue

                chunk_path = self._get_chunk_path(self.world_id, self.current_seed, cx, cz)
                if not (chunk_path / "chunk.rle.json").exists():
                    tasks.append((self.world_id, self.current_seed, cx, cz))
        return tasks

    def _load_or_generate_chunk(self, cx: int, cz: int):
        """Метод для ВОРКЕРА. Генерирует чанк и сохраняет его."""
        chunk_path = self._get_chunk_path(self.world_id, self.current_seed, cx, cz)
        if (chunk_path / "chunk.rle.json").exists():
            return

        t_total_start = time.perf_counter()
        gen_params = {"seed": self.current_seed, "cx": cx, "cz": cz, "world_id": self.world_id}
        result = self.generator.generate(gen_params)

        t_export_start = time.perf_counter()
        meta_path = str(chunk_path / "chunk.meta.json")
        rle_path = str(chunk_path / "chunk.rle.json")
        preview_path = str(chunk_path / "preview.png")

        write_chunk_rle_json(rle_path, result.layers["kind"], result.size, result.seed, cx, cz)
        write_preview_png(preview_path, result.layers["kind"], self.preset.export["palette"])

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
            f"  - Elevation      : {timings.get('elevation', 0):8.2f} ms\n"
            f"  - Connectivity   : {timings.get('connectivity', 0):8.2f} ms\n"
            f"  - Export         : {timings.get('export', 0):8.2f} ms\n"
            f"------------------------------------\n"
            f"  - TOTAL          : {timings.get('total', 0):8.2f} ms"
        )

    def check_and_trigger_transition(self, wx: int, wz: int) -> Tuple[int, int] | None:
        if self.world_id != "city":
            return None

        lx, lz = wx % CHUNK_SIZE, wz % CHUNK_SIZE
        side = None

        if wx == CHUNK_SIZE - 1 and (0 <= wz < CHUNK_SIZE):
            side = "E"
        elif wx == 0 and (0 <= wz < CHUNK_SIZE):
            side = "W"
        elif wz == CHUNK_SIZE - 1 and (0 <= wx < CHUNK_SIZE):
            side = "S"
        elif wz == 0 and (0 <= wx < CHUNK_SIZE):
            side = "N"

        if side:
            chunk_data = self.get_chunk_data(0, 0)
            if chunk_data and chunk_data["kind"][lz][lx] == KIND_GROUND:
                print(f"--- Entering Gateway to Branch: {side} ---")
                self.world_id = f"branch/{side}"
                self.current_seed = self._branch_seed(side)
                self.cache.clear()
                if side == "N":
                    new_cx, new_cz = 0, -1
                elif side == "S":
                    new_cx, new_cz = 0, 1
                elif side == "W":
                    new_cx, new_cz = -1, 0
                else:
                    new_cx, new_cz = 1, 0
                self.player_chunk_cx = new_cx
                self.player_chunk_cz = new_cz
                new_wx = new_cx * CHUNK_SIZE + (CHUNK_SIZE - 1 - lx)
                new_wz = new_cz * CHUNK_SIZE + (CHUNK_SIZE - 1 - lz)
                return (new_wx, new_wz)
        return None