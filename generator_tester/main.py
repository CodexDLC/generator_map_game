# generator_tester/world_manager.py
import hashlib
import json
import pathlib
from typing import Dict, Tuple, Any, List

from engine.worldgen_core.base.preset import Preset
from engine.worldgen_core.world.world_generator import WorldGenerator
from engine.worldgen_core.base.export import write_preview_png, write_chunk_rle_json
from engine.worldgen_core.utils.rle import decode_rle_rows
from engine.worldgen_core.base.constants import ID_TO_KIND, DEFAULT_PALETTE, KIND_GROUND
from generator_tester.config import PRESET_PATH, ARTIFACTS_ROOT, CHUNK_SIZE


class WorldManager:
    def __init__(self, city_seed: int):
        self.city_seed = city_seed
        self.preset = self._load_preset()
        self.generator = WorldGenerator(self.preset)
        self.cache: Dict[Tuple, Dict | None] = {}
        self.preload_radius = 2

        self.world_id = "city"
        self.current_seed = city_seed
        # <<< ИЗМЕНЕНО: Переименовали переменные >>>
        self.cx = 0
        self.cz = 0
        self.city_gateways = self._get_city_gateways()

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

    def _get_city_gateways(self) -> Dict[Tuple[int, int], str]:
        gates = {}
        branches = self.preset.to_dict().get("branches", {})
        mid = CHUNK_SIZE // 2
        if branches.get("N", {}).get("enabled"): gates[(mid, 0)] = "N"
        if branches.get("S", {}).get("enabled"): gates[(mid, CHUNK_SIZE - 1)] = "S"
        if branches.get("W", {}).get("enabled"): gates[(0, mid)] = "W"
        if branches.get("E", {}).get("enabled"): gates[(CHUNK_SIZE - 1, mid)] = "E"
        return gates

    def preload_chunks_around(self, center_cx: int, center_cz: int):
        print(f"--- Preloading grid around ({center_cx}, {center_cz}) ---")
        for dz in range(-self.preload_radius, self.preload_radius + 1):
            for dx in range(-self.preload_radius, self.preload_radius + 1):
                self.get_chunk_data(center_cx + dx, center_cz + dz)

    def get_tile_at(self, wx: int, wz: int) -> Dict:
        cx, cz = wx // CHUNK_SIZE, wz // CHUNK_SIZE
        lx, lz = wx % CHUNK_SIZE, wz % CHUNK_SIZE

        chunk_data = self.get_chunk_data(cx, cz)
        if not chunk_data or not chunk_data.get("kind"):
            return {"kind": "void"}

        kind_grid = chunk_data["kind"]
        kind = kind_grid[lz][lx] if (0 <= lz < len(kind_grid) and 0 <= lx < len(kind_grid[0])) else "void"

        tile_info = {"kind": kind}

        if self.world_id == "city" and cx == 0 and cz == 0 and kind == KIND_GROUND:
            is_border = lx == 0 or lx == CHUNK_SIZE - 1 or lz == 0 or lz == CHUNK_SIZE - 1
            if is_border:
                tile_info["is_gateway"] = True

        return tile_info

    def get_chunk_data(self, cx: int, cz: int) -> Dict | None:
        key = (self.world_id, self.current_seed, cx, cz)
        if key in self.cache:
            return self.cache[key]

        raw_data = self._load_or_generate_chunk(cx, cz)
        if not raw_data:
            self.cache[key] = None
            return None

        kind_payload = raw_data.get("layers", {}).get("kind", {})
        grid_ids = decode_rle_rows(kind_payload.get("rows", []))
        kind_grid = [[ID_TO_KIND.get(v, "ground") for v in row] for row in grid_ids]

        height_grid = raw_data.get("layers", {}).get("height_q", {}).get("grid", [])

        decoded_chunk = {"kind": kind_grid, "height": height_grid}
        self.cache[key] = decoded_chunk
        return decoded_chunk

    def _load_or_generate_chunk(self, cx: int, cz: int) -> Dict | None:
        if self.world_id == "city":
            if cx == 0 and cz == 0:
                city_path = pathlib.Path(ARTIFACTS_ROOT, "world", "city", "static", "0_0", "chunk.rle.json")
                if not city_path.exists(): return None
                with open(city_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return {"layers": {"kind": data}}
            else:
                return None

        chunk_path = self._get_chunk_path(self.world_id, self.current_seed, cx, cz)

        if (chunk_path / "chunk.rle.json").exists():
            with open(chunk_path / "chunk.rle.json", "r", encoding="utf-8") as f: data = json.load(f)
            return {"layers": {"kind": data}}

        print(f"Generating new chunk: {(self.world_id, self.current_seed, cx, cz)}")
        gen_params = {"seed": self.current_seed, "cx": cx, "cz": cz, "world_id": self.world_id}
        result = self.generator.generate(gen_params)

        chunk_path.mkdir(parents=True, exist_ok=True)
        write_chunk_rle_json(str(chunk_path / "chunk.rle.json"), result.layers["kind"], result.size, result.seed, cx,
                             cz)
        write_preview_png(str(chunk_path / "preview.png"), result.layers["kind"], self.preset.export["palette"])

        return result.layers

    def check_and_trigger_transition(self, wx: int, wz: int) -> Tuple[int, int] | None:
        if self.world_id != "city":
            return None

        cx, cz = wx // CHUNK_SIZE, wz // CHUNK_SIZE
        lx, lz = wx % CHUNK_SIZE, wz % CHUNK_SIZE

        if cx != 0 or cz != 0:
            return None

        side = None
        if lx == CHUNK_SIZE - 1:
            side = "E"
        elif lx == 0:
            side = "W"
        elif lz == CHUNK_SIZE - 1:
            side = "S"
        elif lz == 0:
            side = "N"

        if side:
            chunk_data = self.get_chunk_data(0, 0)
            is_walkable_ground = chunk_data and chunk_data["kind"][lz][lx] == KIND_GROUND

            if is_walkable_ground:
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

                # <<< ИЗМЕНЕНО: Обновляем правильные атрибуты >>>
                self.cx = new_cx
                self.cz = new_cz

                new_wx = new_cx * CHUNK_SIZE + (CHUNK_SIZE - 1 - lx)
                new_wz = new_cz * CHUNK_SIZE + (CHUNK_SIZE - 1 - lz)
                return (new_wx, new_wz)

        return None