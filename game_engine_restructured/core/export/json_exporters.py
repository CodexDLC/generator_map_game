# ==============================================================================
# Файл: game_engine_restructured/core/export/json_exporters.py
# Назначение: Функции для записи различных метаданных в формате JSON.
# ==============================================================================
from __future__ import annotations
import dataclasses
import json
import os
from pathlib import Path
from typing import Any, Dict

from ...world.object_types import PlacedObject
from ...world.serialization import ClientChunkContract, RegionMetaContract
from ..utils.rle import encode_rle_rows


def _ensure_path_exists(path: str) -> None:
    """Убеждается, что директория для файла существует."""
    Path(path).parent.mkdir(parents=True, exist_ok=True)


def _atomic_write_json(path: str, data: Any, verbose: bool = False):
    """Атомарно записывает данные в JSON файл для предотвращения битых файлов."""
    _ensure_path_exists(path)
    tmp_path = path + ".tmp"

    def default_serializer(o):
        if dataclasses.is_dataclass(o):
            return dataclasses.asdict(o)
        try:
            import numpy as _np
            if isinstance(o, _np.integer): return int(o)
            if isinstance(o, _np.floating): return float(o)
        except ImportError:
            pass
        raise TypeError(f"Object of type {type(o).__name__} is not JSON serializable")

    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=default_serializer)
    os.replace(tmp_path, path)
    if verbose:
        print(f"--- EXPORT: JSON file saved: {path}")


def write_region_meta(
    path: str, meta_contract: RegionMetaContract, verbose: bool = False
):
    """Записывает метаданные региона."""
    data = dataclasses.asdict(meta_contract)
    if "road_plan" in data and meta_contract.road_plan:
        data["road_plan"] = {
            f"{k[0]},{k[1]}": v for k, v in meta_contract.road_plan.items()
        }
    _atomic_write_json(path, data, verbose)


def write_client_chunk_meta(
    path: str, chunk_contract: ClientChunkContract, verbose: bool = False
):
    """Записывает метаданные чанка для клиента."""
    data = {
        "version": chunk_contract.version,
        "cx": chunk_contract.cx,
        "cz": chunk_contract.cz,
        "grid": chunk_contract.grid,
        "files": {
            "heightmap": "heightmap.r16",
            "controlmap": "control.r32",
            "objects": "objects.json",
        },
    }
    _atomic_write_json(path, data, verbose)


def write_objects_json(path: str, objects: list[PlacedObject], verbose: bool = False):
    """Записывает список размещенных объектов."""
    data = [
        {
            "id": obj.prefab_id,
            "center_hex": {"q": obj.center_q, "r": obj.center_r},
            "rotation": round(obj.rotation, 2),
            "scale": obj.scale,
        }
        for obj in objects
    ]
    _atomic_write_json(path, data, verbose)


def write_world_meta_json(path: str, **kwargs) -> None:
    """Записывает глобальные метаданные мира."""
    data = {
        "version": "world_meta_v1",
        "world_id": kwargs.get("world_id"),
        "grid": {
            "type": "hex", "orientation": "pointy-top", "coord_logic": "axial",
            "coord_storage": "odd-r", "hex_edge_m": kwargs.get("hex_edge_m"),
        },
        "terrain": {
            "chunk_px": kwargs.get("chunk_px"),
            "meters_per_pixel": kwargs.get("meters_per_pixel"),
            "height_encoding": {
                "format": "R16_raw_norm_max",
                "height_min_m": kwargs.get("height_min_m"),
                "height_max_m": kwargs.get("height_max_m"),
            },
        },
    }
    _atomic_write_json(path, data)


def write_navigation_rle(
    path: str, nav_grid: list[list[str]], grid_spec: Any, verbose: bool = False
):
    """Записывает навигационную сетку в RLE-сжатом формате."""
    from ..constants import NAV_KIND_TO_ID
    try:
        h = len(nav_grid)
        w = len(nav_grid[0]) if h > 0 else 0
        if w == 0: return

        id_grid = [[NAV_KIND_TO_ID.get(kind, 1) for kind in row] for row in nav_grid]
        cols, rows = grid_spec.dims_for_chunk() if grid_spec else (w, h)
        data = {
            "version": "nav_rle_v1", "size": {"cols": cols, "rows": rows},
            "legend": {"0": "passable", "1": "obstacle_prop", "2": "water", "7": "bridge"},
            "rows": encode_rle_rows(id_grid)["rows"],
        }
        _atomic_write_json(path, data, verbose)
    except Exception as e:
        print(f"!!! LOG: CRITICAL ERROR while creating navigation.rle.json: {e}")


def write_server_hex_map(path: str, hex_map_data: Dict[str, Any]):
    """Записывает карту гексов для сервера."""
    data = {
        "version": "server_hex_v1",
        "origin_axial": {"q": 0, "r": 0},
        "cells": hex_map_data,
    }
    _atomic_write_json(path, data)