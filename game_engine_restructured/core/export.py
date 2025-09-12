# game_engine_restructured/core/export.py
from __future__ import annotations
import json
import os
from typing import Any, Dict, List, Tuple
from pathlib import Path
import dataclasses

from .utils.rle import encode_rle_rows
from ..world.serialization import RegionMetaContract, ClientChunkContract
from ..world.object_types import PlacedObject
from .constants import SURFACE_KIND_TO_ID, NAV_KIND_TO_ID, SURFACE_ID_TO_KIND, NAV_ID_TO_KIND
from .types import GenResult

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


def _atomic_write_json(path: str, data: Any, verbose: bool = False):
    _ensure_path_exists(path)
    tmp_path = path + ".tmp"

    def default_serializer(o):
        if dataclasses.is_dataclass(o):
            return dataclasses.asdict(o)
        raise TypeError(f"Object of type {type(o).__name__} is not JSON serializable")

    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=default_serializer)
    os.replace(tmp_path, path)
    if verbose:
        print(f"--- EXPORT: JSON file saved: {path}")


def write_raw_chunk(path_prefix: str, chunk_data: GenResult):
    if not NUMPY_OK: return
    meta_path = path_prefix + ".meta.json"
    grid_path = path_prefix + ".npz"
    meta = {
        "version": chunk_data.version, "type": chunk_data.type,
        "seed": chunk_data.seed, "cx": chunk_data.cx, "cz": chunk_data.cz,
        "size": chunk_data.size, "cell_size": chunk_data.cell_size,
        "grid_spec": dataclasses.asdict(chunk_data.grid_spec) if chunk_data.grid_spec else None,
        "stage_seeds": chunk_data.stage_seeds,
    }
    _atomic_write_json(meta_path, meta)
    height_grid = np.array(chunk_data.layers.get("height_q", {}).get("grid", []), dtype=np.float32)
    surface_str = chunk_data.layers.get("surface", [])
    surface_ids = np.array([[SURFACE_KIND_TO_ID.get(kind, 0) for kind in row] for row in surface_str], dtype=np.uint8)
    nav_str = chunk_data.layers.get("navigation", [])
    nav_ids = np.array([[NAV_KIND_TO_ID.get(kind, 1) for kind in row] for row in nav_str], dtype=np.uint8)
    _ensure_path_exists(grid_path)
    tmp_path = grid_path + ".tmp"
    with open(tmp_path, "wb") as f:
        np.savez_compressed(f, height=height_grid, surface=surface_ids, navigation=nav_ids)
    os.replace(tmp_path, grid_path)


# --- НАЧАЛО ИЗМЕНЕНИЙ ---
def write_raw_regional_layers(path: str, layers: Dict[str, np.ndarray], verbose: bool = False):
    """
    Сохраняет "сырые" слои региона (например, климат) в один сжатый
    бинарный .npz файл для максимальной эффективности.
    """
    if not NUMPY_OK: return
    _ensure_path_exists(path)
    tmp_path = path + ".tmp"
    try:
        # Используем более надежный метод: сначала открываем файл, потом передаем его в numpy
        with open(tmp_path, 'wb') as f:
            np.savez_compressed(f, **layers)

        os.replace(tmp_path, path)

        if verbose:
            print(f"--- EXPORT: Raw regional layers saved to: {path}")
    except Exception as e:
        print(f"!!! LOG: CRITICAL ERROR while creating raw regional file {path}: {e}")


# --- КОНЕЦ ИЗМЕНЕНИЙ ---


def read_raw_chunk(path_prefix: str) -> GenResult | None:
    if not NUMPY_OK: return None
    meta_path = path_prefix + ".meta.json"
    grid_path = path_prefix + ".npz"
    if not os.path.exists(meta_path) or not os.path.exists(grid_path):
        return None
    try:
        with open(meta_path, "r", encoding="utf-8") as f:
            meta = json.load(f)
        with np.load(grid_path) as grid_data:
            height_grid = grid_data['height'].tolist()
            surface_ids = grid_data['surface']
            surface_str = [[SURFACE_ID_TO_KIND.get(int(id_val), "base_dirt") for id_val in row] for row in surface_ids]
            nav_ids = grid_data['navigation']
            nav_str = [[NAV_ID_TO_KIND.get(int(id_val), "obstacle_prop") for id_val in row] for row in nav_ids]
        from ..core.grid.hex import HexGridSpec
        grid_spec = HexGridSpec(**meta['grid_spec']) if meta.get('grid_spec') else None
        result = GenResult(
            version=meta['version'], type=meta['type'], seed=meta['seed'],
            cx=meta['cx'], cz=meta['cz'], size=meta['size'], cell_size=meta['cell_size'],
            grid_spec=grid_spec, stage_seeds=meta['stage_seeds'],
            layers={
                "height_q": {"grid": height_grid},
                "surface": surface_str,
                "navigation": nav_str,
                "overlay": [[0 for _ in range(meta['size'])] for _ in range(meta['size'])]
            }
        )
        return result
    except Exception as e:
        print(f"!!! ERROR reading raw chunk {path_prefix}: {e}")
        return None


def write_region_meta(path: str, meta_contract: RegionMetaContract, verbose: bool = False):
    data_to_serialize = dataclasses.asdict(meta_contract)
    if "road_plan" in data_to_serialize and meta_contract.road_plan:
        serializable_road_plan = {f"{k[0]},{k[1]}": v for k, v in meta_contract.road_plan.items()}
        data_to_serialize["road_plan"] = serializable_road_plan
    _atomic_write_json(path, data_to_serialize, verbose=verbose)
    if verbose:
        print(f"--- EXPORT: Метаданные региона сохранены: {path}")


def write_client_chunk_meta(path: str, chunk_contract: ClientChunkContract, verbose: bool = False):
    output_data = {
        "version": chunk_contract.version, "cx": chunk_contract.cx, "cz": chunk_contract.cz,
        "grid": chunk_contract.grid,
        "files": {"heightmap": "heightmap.r16", "controlmap": "control.r32", "objects": "objects.json"}
    }
    _atomic_write_json(path, output_data, verbose=verbose)


def write_objects_json(path: str, objects: list[PlacedObject], verbose: bool = False):
    serializable_objects = [{
        "id": obj.prefab_id,
        "center_hex": {"q": obj.center_q, "r": obj.center_r},
        "rotation": round(obj.rotation, 2),
        "scale": obj.scale
    } for obj in objects]
    _atomic_write_json(path, serializable_objects, verbose=verbose)


def write_chunk_preview(path: str, surface_grid: List[List[str]], nav_grid: List[List[str]], palette: Dict[str, str],
                        verbose: bool = False):
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
        img_resized = img.resize((w * 2, h * 2), Image.Resampling.NEAREST)
        _ensure_path_exists(path)
        tmp_path = path + ".tmp"
        img_resized.save(tmp_path, format="PNG")
        os.replace(tmp_path, path)
        if verbose:
            print(f"--- EXPORT: Preview image saved: {path}")
    except Exception as e:
        print(f"!!! LOG: CRITICAL ERROR while creating preview.png: {e}")


def _pack_control_data(base_id=0, overlay_id=0, blend=0, nav=True) -> np.uint32:
    val = 0
    val |= (base_id & 0x1F) << 27
    val |= (overlay_id & 0x1F) << 22
    val |= (blend & 0xFF) << 14
    if nav: val |= 1 << 3
    return np.uint32(val)


def write_heightmap_r16(path: str, height_grid: List[List[float]], max_height: float, verbose: bool = False):
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
        if verbose:
            print(f"--- EXPORT: 16-bit UINT heightmap saved: {path}")
    except Exception as e:
        print(f"!!! LOG: CRITICAL ERROR while creating heightmap.r16: {e}")


def write_control_map_r32(path: str, surface_grid: List[List[str]], nav_grid: List[List[str]],
                          overlay_grid: List[List[int]], verbose: bool = False):
    if not NUMPY_OK: return
    try:
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
        if verbose:
            print(f"--- EXPORT: Binary Control map (.r32) saved: {path}")
    except Exception as e:
        print(f"!!! LOG: CRITICAL ERROR while creating control.r32: {e}")


def write_world_meta_json(path: str, *, world_id: Any, hex_edge_m: float, meters_per_pixel: float, chunk_px: int,
                          height_min_m: float, height_max_m: float, **kwargs) -> None:
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


def write_navigation_rle(path: str, nav_grid: List[List[str]], grid_spec: Any, verbose: bool = False):
    if not NUMPY_OK: return
    try:
        h = len(nav_grid)
        w = len(nav_grid[0]) if h > 0 else 0
        if w == 0 or h == 0: return
        id_grid = [[NAV_KIND_TO_ID.get(kind, 1) for kind in row] for row in nav_grid]
        rle_rows = encode_rle_rows(id_grid)["rows"]
        cols, rows = grid_spec.dims_for_chunk() if grid_spec else (w, h)
        output_data = {
            "version": "nav_rle_v1",
            "storage": {"coord": "odd-r", "origin_axial": {"q": 0, "r": 0}},
            "size": {"cols": cols, "rows": rows},
            "legend": {"0": "passable", "1": "obstacle_prop", "2": "water", "7": "bridge"},
            "rows": rle_rows
        }
        _atomic_write_json(path, output_data, verbose=verbose)
    except Exception as e:
        print(f"!!! LOG: CRITICAL ERROR while creating navigation.rle.json: {e}")


def write_server_hex_map(path: str, hex_map_data: Dict[str, Any]):
    output_data = {
        "version": "server_hex_v1",
        "origin_axial": {"q": 0, "r": 0},
        "cells": hex_map_data
    }
    try:
        _atomic_write_json(path, output_data)
        print(f"--- EXPORT: Серверная карта гексов (.json) сохранена: {path}")
    except Exception as e:
        print(f"!!! LOG: КРИТИЧЕСКАЯ ОШИБКА при создании server_hex_map.json: {e}")