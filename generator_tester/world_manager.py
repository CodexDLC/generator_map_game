# generator_tester/world_manager.py
# ... (импорты и большая часть класса без изменений) ...
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
from game_logic.transition_manager import WorldTransitionManager


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

        self.transition_manager = WorldTransitionManager(self)

    def get_chunk_data(self, cx: int, cz: int) -> Dict | None:
        key = (self.world_id, self.current_seed, cx, cz)
        if key in self.cache:
            return self.cache[key]

        rle_path: pathlib.Path

        if self.world_id == "city":
            if cx == 0 and cz == 0:
                rle_path = ARTIFACTS_ROOT / "world" / "city" / "static" / "0_0" / "chunk.rle.json"
                try:
                    with open(rle_path, "r") as f:
                        city_data = json.load(f)
                    kind_grid_ids = decode_rle_rows(city_data.get("rows", []))
                    kind_grid = [[ID_TO_KIND.get(v, "ground") for v in row] for row in kind_grid_ids]
                    height_grid = [[0] * len(kind_grid) for _ in range(len(kind_grid))]
                    decoded_chunk = {"kind": kind_grid, "height": height_grid}
                    self.cache[key] = decoded_chunk
                    return decoded_chunk
                except (json.JSONDecodeError, FileNotFoundError):
                    return None
            else:
                return None
        else:
            chunk_path = self._get_chunk_path(self.world_id, self.current_seed, cx, cz)
            rle_path = chunk_path / "chunk.rle.json"

        if not rle_path.exists():
            return None

        try:
            with open(rle_path, "r", encoding="utf-8") as f:
                rle_doc = json.load(f)

            layers_data = rle_doc.get("layers", {})
            kind_payload = layers_data.get("kind", {})
            height_payload = layers_data.get("height_q", {})

            kind_grid = decode_rle_rows(kind_payload.get("rows", []))
            height_grid = decode_rle_rows(height_payload.get("rows", []))

            decoded_chunk = {"kind": kind_grid, "height": height_grid}

            self.cache[key] = decoded_chunk
            return decoded_chunk

        except (json.JSONDecodeError, IndexError, KeyError) as e:
            print(f"Warning: Could not decode chunk at {rle_path}. Error: {e}")
            return None

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

    # <<< =============== ИСПРАВЛЕНИЕ ОШИБКИ ВОРКЕРА =============== >>>
    def _load_or_generate_chunk(self, cx: int, cz: int):
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

        # Здесь была ошибка: в write_chunk_rle_json нужно было передавать result.layers (словарь),
        # а не result.layers['kind'] (список).
        write_chunk_rle_json(rle_path, result.layers, result.size, result.seed, cx, cz)
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