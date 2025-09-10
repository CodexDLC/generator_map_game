# game_engine/core/export.py
from __future__ import annotations
import json
import os
from typing import Any, Dict, List, Tuple
from pathlib import Path
import dataclasses

from .utils.rle import encode_rle_rows
from ..world_structure.serialization import RegionMetaContract, ClientChunkContract
from ..world_structure.object_types import PlacedObject
from .constants import SURFACE_KIND_TO_ID, NAV_KIND_TO_ID  # <-- Убрал лишний импорт NAV_KIND_TO_ID

NUMPY_OK = False
PIL_OK = False
try:
    import numpy as np

    NUMPY_OK = True
except ImportError:
    pass
try:
    from PIL import Image

    PIL_OK = True
except ImportError:
    pass


def _ensure_path_exists(path: str) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)


def _atomic_write_json(path: str, data: Any):
    _ensure_path_exists(path)
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
    if "road_plan" in data_to_serialize and meta_contract.road_plan:
        serializable_road_plan = {f"{k[0]},{k[1]}": v for k, v in meta_contract.road_plan.items()}
        data_to_serialize["road_plan"] = serializable_road_plan
    _atomic_write_json(path, data_to_serialize)
    print(f"--- EXPORT: Метаданные региона сохранены: {path}")


def write_client_chunk_meta(path: str, chunk_contract: ClientChunkContract):
    output_data = {
        "version": chunk_contract.version, "cx": chunk_contract.cx, "cz": chunk_contract.cz,
        "grid": chunk_contract.grid,
        "files": {"heightmap": "heightmap.r16", "controlmap": "control.r32", "objects": "objects.json"}
    }
    _atomic_write_json(path, output_data)
    print(f"--- EXPORT: Мета-файл чанка сохранен: {path}")


def write_objects_json(path: str, objects: list[PlacedObject]):
    serializable_objects = [{
        "id": obj.prefab_id,
        "center_hex": {"q": obj.center_q, "r": obj.center_r},
        "rotation": round(obj.rotation, 2),
        "scale": obj.scale
    } for obj in objects]
    _atomic_write_json(path, serializable_objects)
    print(f"--- EXPORT: Список объектов сохранен: {path}")


def write_chunk_preview(
        path: str, surface_grid: List[List[str]], nav_grid: List[List[str]], palette: Dict[str, str],
):
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
                px[x, z] = hex_to_rgb(palette.get(surface_grid[z][x], "#FF00FF"))
        for z in range(h):
            for x in range(w):
                if nav_grid[z][x] != "passable":
                    px[x, z] = hex_to_rgb(palette.get(nav_grid[z][x], "#FF00FF"))

        # --- ИСПРАВЛЕНИЕ: Используем новый синтаксис для NEAREST ---
        img_resized = img.resize((w * 2, h * 2), Image.Resampling.NEAREST)

        _ensure_path_exists(path)
        tmp_path = path + ".tmp"
        img_resized.save(tmp_path, format="PNG")
        os.replace(tmp_path, path)
    except Exception as e:
        print(f"!!! LOG: КРИТИЧЕСКАЯ ОШИБКА при создании preview.png: {e}")


def write_heightmap_r16(path: str, height_grid: List[List[float]], max_height: float):
    if not NUMPY_OK: return
    try:
        if not height_grid or not height_grid[0]: return
        if max_height <= 0: max_height = 1.0
        height_array = np.array(height_grid, dtype=np.float32)
        normalized = np.clip(height_array / max_height, 0.0, 1.0)
        final_array = (normalized * 65535.0).astype("<u2")
        _ensure_path_exists(path)
        tmp_path = path + ".tmp"
        with open(tmp_path, "wb") as f:
            f.write(final_array.tobytes())
        os.replace(tmp_path, path)
        print(f"--- EXPORT: 16-битный UINT heightmap сохранён: {path}")
    except Exception as e:
        print(f"!!! LOG: КРИТИЧЕСКАЯ ОШИБКА при создании heightmap.r16: {e}")


def _pack_control_data(base_id=0, overlay_id=0, blend=0, nav=True) -> np.uint32:
    val = 0
    val |= (base_id & 0x1F) << 27
    val |= (overlay_id & 0x1F) << 22
    val |= (blend & 0xFF) << 14
    if nav: val |= 1 << 3
    return np.uint32(val)


def write_control_map_r32(
        path: str, surface_grid: List[List[str]], nav_grid: List[List[str]], overlay_grid: List[List[int]],
):
    if not NUMPY_OK: return
    try:
        # --- ИСПРАВЛЕНИЕ: Разделяем определение h и w ---
        h = len(surface_grid)
        w = len(surface_grid[0]) if h > 0 else 0
        if w == 0 or h == 0: return

        control_map = np.zeros((h, w), dtype="<u4")
        for z in range(h):
            for x in range(w):
                base_id = SURFACE_KIND_TO_ID.get(surface_grid[z][x], 0)
                is_navigable = nav_grid[z][x] in ("passable", "bridge")
                blend = 255 if overlay_grid[z][x] != 0 else 0
                control_map[z, x] = _pack_control_data(
                    base_id=base_id, overlay_id=overlay_grid[z][x], blend=blend, nav=is_navigable,
                )
        _ensure_path_exists(path)
        tmp_path = path + ".tmp"
        with open(tmp_path, "wb") as f:
            f.write(control_map.tobytes())
        os.replace(tmp_path, path)
        print(f"--- EXPORT: Бинарная Control map (.r32) сохранена: {path}")
    except Exception as e:
        print(f"!!! LOG: КРИТИЧЕСКАЯ ОШИБКА при создании control.r32: {e}")


def write_world_meta_json(
        path: str, *, world_id: Any, hex_edge_m: float, meters_per_pixel: float, chunk_px: int,
        height_min_m: float, height_max_m: float, **kwargs
) -> None:
    _ensure_path_exists(path)
    data = {
        "version": "world_meta_v1", "world_id": world_id,
        "grid": {"type": "hex", "orientation": "pointy-top", "coord_logic": "axial",
                 "coord_storage": "odd-r", "hex_edge_m": hex_edge_m},
        "terrain": {"chunk_px": chunk_px, "meters_per_pixel": meters_per_pixel,
                    "height_encoding": {"format": "R16_raw_norm_max", "height_min_m": height_min_m,
                                        "height_max_m": height_max_m},
                    "stream_window": {"cols": 5, "rows": 5}},
        "assets": {"url_pattern": f"/world/v2_hex/{world_id}/{{scx}}_{{scz}}/{{cx}}_{{cz}}/",
                   "filenames": {"height": "height_rev{rev}.r16", "control": "control_rev{rev}.r32"}}
    }
    _atomic_write_json(path, data)
    print(f"--- EXPORT: world meta сохранён: {path}")


def write_navigation_rle(path: str, nav_grid: List[List[str]], grid_spec: Any):
    """
    Сохраняет навигационную сетку в виде RLE-закодированного JSON файла с числовыми ID.
    Это формат для серверного использования.
    """
    if not NUMPY_OK: return
    try:
        h = len(nav_grid)
        w = len(nav_grid[0]) if h > 0 else 0
        if w == 0 or h == 0: return

        id_grid = [[NAV_KIND_TO_ID.get(kind, 1) for kind in row] for row in nav_grid]  # 1 - obstacle по-умолчанию
        rle_rows = encode_rle_rows(id_grid)["rows"]

        # --- НОВАЯ СТРУКТУРА ФАЙЛА ---
        cols, rows = grid_spec.dims_for_chunk() if grid_spec else (w, h)

        output_data = {
            "version": "nav_rle_v1",
            "storage": {"coord": "odd-r", "origin_axial": {"q": 0, "r": 0}},
            "size": {"cols": cols, "rows": rows},
            "legend": {
                "0": "passable",
                "1": "obstacle_prop",
                "2": "water",
                "7": "bridge"
            },
            "rows": rle_rows
        }
        # -----------------------------

        _atomic_write_json(path, output_data)
        print(f"--- EXPORT: Серверная навигационная карта (.rle.json) сохранена: {path}")

    except Exception as e:
        print(f"!!! LOG: КРИТИЧЕСКАЯ ОШИБКА при создании navigation.rle.json: {e}")


def write_server_hex_map(path: str, hex_map_data: Dict[str, Any]):
    """
    Сохраняет детальную карту гексов в виде JSON-файла для серверного использования.
    """
    # --- НОВАЯ СТРУКТУРА ФАЙЛА ---
    output_data = {
        "version": "server_hex_v1",
        "origin_axial": {"q": 0, "r": 0}, # Координаты гексов даны относительно этого начала
        "cells": hex_map_data
    }
    # -----------------------------
    try:
        _atomic_write_json(path, output_data)
        print(f"--- EXPORT: Серверная карта гексов (.json) сохранена: {path}")
    except Exception as e:
        print(f"!!! LOG: КРИТИЧЕСКАЯ ОШИБКА при создании server_hex_map.json: {e}")