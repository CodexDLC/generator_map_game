# Замените ВСЁ содержимое файла game_engine/core/export.py на этот код:
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
    NUMPY_OK = False

try:
    from PIL import Image

    PIL_OK = True
except ImportError:
    PIL_OK = False

from ..world_structure.serialization import RegionMetaContract, ClientChunkContract
from .constants import ID_TO_KIND, KIND_TO_ID


def _atomic_write_json(path: str, data: Any):
    """Атомарная запись JSON, которая теперь корректно перезаписывает файлы."""
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path + ".tmp"

    def default_serializer(o):
        if dataclasses.is_dataclass(o):
            return dataclasses.asdict(o)
        raise TypeError(f"Object of type {type(o).__name__} is not JSON serializable")

    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=default_serializer)

    # --- КЛЮЧЕВОЕ ИСПРАВЛЕНИЕ: Используем os.replace вместо os.rename ---
    # Это атомарно и правильно обрабатывает перезапись существующего файла.
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
    for layer_name, grid_data in chunk_contract.layers.items():
        if layer_name == "kind":
            id_grid = [[KIND_TO_ID.get(kind, 4) for kind in row] for row in grid_data]
            output_data["layers"][layer_name] = encode_rle_rows(id_grid)
        elif layer_name == "height_q" and isinstance(grid_data, dict) and "grid" in grid_data:
            output_data["layers"][layer_name] = encode_rle_rows(grid_data["grid"])
    _atomic_write_json(path, output_data)


def write_chunk_preview(path: str, kind_grid: List[List[Any]], palette: Dict[str, str]):
    if not PIL_OK: return
    try:
        h = len(kind_grid)
        w = len(kind_grid[0]) if h else 0
        if w == 0 or h == 0: return

        def hex_to_rgb(s: str) -> Tuple[int, int, int]:
            s = s.lstrip("#")
            return int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16)

        def to_rgb(v: Any) -> Tuple[int, int, int]:
            name = v if isinstance(v, str) else ID_TO_KIND.get(int(v), "ground")
            return hex_to_rgb(palette.get(name, "#000000"))

        img = Image.new("RGB", (w * 2, h * 2))
        px = img.load()
        for z in range(h):
            for x in range(w):
                color = to_rgb(kind_grid[z][x])
                for dx in range(2):
                    for dy in range(2):
                        px[x * 2 + dx, z * 2 + dy] = color
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        tmp_path = path + ".tmp"
        img.save(tmp_path, format="PNG")
        os.replace(tmp_path, path)
    except Exception as e:
        print(f"!!! LOG: КРИТИЧЕСКАЯ ОШИБКА при создании preview.png: {e}")


def write_heightmap_r16(path: str, height_grid: List[List[float]], max_height: float):
    if not NUMPY_OK:
        print("!!! LOG: NumPy не найден, не могу сохранить .r16."); return
    try:
        if not height_grid or not height_grid[0]:
            return
        if max_height <= 0:
            max_height = 1.0

        height_array = np.array(height_grid, dtype=np.float32)
        normalized = np.clip(height_array / max_height, 0.0, 1.0)

        # Было: float16  -> НЕ надо
        # final_array = normalized.astype(np.float16)

        # Стало: little-endian uint16 0..65535
        final_array = (normalized * 65535.0).astype('<u2')  # <u2 == little-endian uint16

        Path(path).parent.mkdir(parents=True, exist_ok=True)
        tmp_path = path + ".tmp"
        with open(tmp_path, 'wb') as f:
            f.write(final_array.tobytes())
        os.replace(tmp_path, path)
        print(f"--- EXPORT: 16-битный UINT heightmap (нормализованный) сохранён: {path}")
    except Exception as e:
        print(f"!!! LOG: КРИТИЧЕСКАЯ ОШИБКА при создании heightmap.r16: {e}")

def _pack_control_data(base_id=0, overlay_id=0, blend8=0, uv_rot=0, uv_scale=0, nav=True, hole=False,
                       auto=False) -> np.uint32:
    val = 0
    val |= (base_id & 0x1F)
    val |= (overlay_id & 0x1F) << 5
    val |= (blend8 & 0xFF) << 10
    val |= (uv_rot & 0x03) << 18
    val |= (uv_scale & 0x07) << 20
    if nav: val |= 1 << 28
    if hole: val |= 1 << 29
    if auto: val |= 1 << 30
    return np.uint32(val)


def write_control_map_r32(path: str, kind_grid: List[List[str]]):
    if not NUMPY_OK: print("!!! LOG: NumPy не найден, не могу сохранить .r32."); return
    try:
        h = len(kind_grid)
        w = len(kind_grid[0]) if h > 0 else 0
        if w == 0 or h == 0: return
        control_map = np.zeros((h, w), dtype=np.uint32)
        for z in range(h):
            for x in range(w):
                kind = kind_grid[z][x]
                base_id = KIND_TO_ID.get(kind, 0)
                control_map[z, x] = _pack_control_data(base_id=base_id)
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        tmp_path = path + ".tmp"
        with open(tmp_path, 'wb') as f:
            f.write(control_map.tobytes())
        os.replace(tmp_path, path)
        print(f"--- EXPORT: Бинарная Control map (.r32) сохранена: {path}")
    except Exception as e:
        print(f"!!! LOG: КРИТИЧЕСКАЯ ОШИБКА при создании control.r32: {e}")

