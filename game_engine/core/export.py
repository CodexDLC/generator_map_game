# game_engine/core/export.py
from __future__ import annotations
import json
import os
from typing import Any, Dict, List, Tuple
from pathlib import Path
import dataclasses

from .utils.rle import encode_rle_rows

try:
    import numpy as np
    NUMPY_OK = True
except ImportError:
    PIL_OK = False

try:
    from PIL import Image
    PIL_OK = True
except ImportError:
    PIL_OK = False

from ..world_structure.serialization import RegionMetaContract, ClientChunkContract
from .constants import (
    SURFACE_KIND_TO_ID, NAV_KIND_TO_ID, DEFAULT_PALETTE
)

# --- НОВАЯ ВСПОМОГАТЕЛЬНАЯ ФУНКЦИЯ ---
def _ensure_path_exists(path: str) -> None:
    """Убеждается, что директория для указанного пути к файлу существует."""
    Path(path).parent.mkdir(parents=True, exist_ok=True)

# -----------------------------------------

def _atomic_write_json(path: str, data: Any):
    _ensure_path_exists(path) # <-- Используем новую функцию
    tmp_path = path + ".tmp"
    def default_serializer(o):
        if dataclasses.is_dataclass(o):
            return dataclasses.asdict(o)
        raise TypeError(f"Object of type {type(o).__name__} is not JSON serializable")
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=default_serializer)
    os.replace(tmp_path, path)


def write_region_meta(path: str, meta_contract: RegionMetaContract):
    data_to_serialize = dataclasses.asdict(meta_contract)
    if 'road_plan' in data_to_serialize and meta_contract.road_plan:
        serializable_road_plan = {f"{k[0]},{k[1]}": v for k, v in meta_contract.road_plan.items()}
        data_to_serialize['road_plan'] = serializable_road_plan
    _atomic_write_json(path, data_to_serialize)
    print(f"--- EXPORT: Метаданные региона сохранены: {path}")


def write_client_chunk(path: str, chunk_contract: ClientChunkContract):
    output_data = {"version": chunk_contract.version, "cx": chunk_contract.cx, "cz": chunk_contract.cz, "layers": {}}
    if "surface" in chunk_contract.layers:
        surface_grid = chunk_contract.layers["surface"]
        id_grid = [[SURFACE_KIND_TO_ID.get(kind, 0) for kind in row] for row in surface_grid]
        output_data["layers"]["surface"] = encode_rle_rows(id_grid)
    if "navigation" in chunk_contract.layers:
        nav_grid = chunk_contract.layers["navigation"]
        id_grid = [[NAV_KIND_TO_ID.get(kind, 0) for kind in row] for row in nav_grid]
        output_data["layers"]["navigation"] = encode_rle_rows(id_grid)
    if "height_q" in chunk_contract.layers and isinstance(chunk_contract.layers["height_q"], dict):
        height_grid = chunk_contract.layers["height_q"].get("grid", [])
        output_data["layers"]["height_q"] = encode_rle_rows(height_grid)
    _atomic_write_json(path, output_data)


def write_chunk_preview(path: str, surface_grid: List[List[str]], nav_grid: List[List[str]], palette: Dict[str, str]):
    if not PIL_OK: return
    try:
        h = len(surface_grid)
        w = len(surface_grid[0]) if h else 0
        if w == 0 or h == 0: return

        def hex_to_rgb(s: str) -> Tuple[int, int, int, int]:
            s = s.lstrip("#")
            if len(s) == 8: return int(s[2:4], 16), int(s[4:6], 16), int(s[6:8], 16), int(s[0:2], 16)
            return int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16), 255

        img = Image.new("RGBA", (w, h))
        px = img.load()
        for z in range(h):
            for x in range(w):
                color = hex_to_rgb(palette.get(surface_grid[z][x], "#FF00FF"))
                px[x, z] = color
        for z in range(h):
            for x in range(w):
                nav_kind = nav_grid[z][x]
                if nav_kind != "passable":
                    color = hex_to_rgb(palette.get(nav_kind, "#FF00FF"))
                    px[x, z] = color

        img_resized = img.resize((w * 2, h * 2), Image.NEAREST)
        _ensure_path_exists(path) # <-- Используем новую функцию
        tmp_path = path + ".tmp"
        img_resized.save(tmp_path, format="PNG")
        os.replace(tmp_path, path)
    except Exception as e:
        print(f"!!! LOG: КРИТИЧЕСКАЯ ОШИБКА при создании preview.png: {e}")


def write_heightmap_r16(path: str, height_grid: List[List[float]], max_height: float):
    if not NUMPY_OK: print("!!! LOG: NumPy не найден, не могу сохранить .r16."); return
    try:
        if not height_grid or not height_grid[0]: return
        if max_height <= 0: max_height = 1.0
        height_array = np.array(height_grid, dtype=np.float32)
        normalized = np.clip(height_array / max_height, 0.0, 1.0)
        final_array = (normalized * 65535.0).astype('<u2')
        _ensure_path_exists(path) # <-- Используем новую функцию
        tmp_path = path + ".tmp"
        with open(tmp_path, 'wb') as f: f.write(final_array.tobytes())
        os.replace(tmp_path, path)
        print(f"--- EXPORT: 16-битный UINT heightmap (нормализованный) сохранён: {path}")
    except Exception as e:
        print(f"!!! LOG: КРИТИЧЕСКАЯ ОШИБКА при создании heightmap.r16: {e}")


def _pack_control_data(base_id=0, nav=True) -> np.uint32:
    val = 0
    val |= (base_id & 0x1F)
    if nav: val |= 1 << 28
    return np.uint32(val)


def write_control_map_r32(path: str, surface_grid: List[List[str]], nav_grid: List[List[str]]):
    if not NUMPY_OK: print("!!! LOG: NumPy не найден, не могу сохранить .r32."); return
    try:
        h = len(surface_grid)
        w = len(surface_grid[0]) if h > 0 else 0
        if w == 0 or h == 0: return
        control_map = np.zeros((h, w), dtype=np.uint32)
        for z in range(h):
            for x in range(w):
                surface_kind = surface_grid[z][x]
                nav_kind = nav_grid[z][x]
                base_id = SURFACE_KIND_TO_ID.get(surface_kind, 0)
                is_navigable = nav_kind == "passable" or nav_kind == "bridge"
                control_map[z, x] = _pack_control_data(base_id=base_id, nav=is_navigable)
        _ensure_path_exists(path) # <-- Используем новую функцию
        tmp_path = path + ".tmp"
        with open(tmp_path, 'wb') as f:
            f.write(control_map.tobytes())
        os.replace(tmp_path, path)
        print(f"--- EXPORT: Бинарная Control map (.r32) сохранена: {path}")
    except Exception as e:
        print(f"!!! LOG: КРИТИЧЕСКАЯ ОШИБКА при создании control.r32: {e}")