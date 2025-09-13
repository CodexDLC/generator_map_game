# ==============================================================================
# Файл: game_engine_restructured/core/export/numpy_exporters.py
# Назначение: Функции для сохранения/загрузки "сырых" данных чанков (NPZ).
# ВЕРСЯ 2.1: Исправлена ошибка с переименованием временного файла .npz.
# ==============================================================================
from __future__ import annotations
import dataclasses
import json
import os
from pathlib import Path
from typing import Dict

import numpy as np

from ..grid.hex import HexGridSpec
from ..types import GenResult


# --- Вспомогательные функции, которые нам понадобятся ---

def _ensure_path_exists(path: str) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)


def _atomic_write_json(path: str, data: any, verbose: bool = False):
    _ensure_path_exists(path)
    tmp_path = path + ".tmp"

    def serializer(o):
        if dataclasses.is_dataclass(o): return dataclasses.asdict(o)
        raise TypeError(f"Object of type {type(o).__name__} is not JSON serializable")

    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=serializer)
    os.replace(tmp_path, path)
    if verbose: print(f"--- EXPORT: JSON file saved: {path}")


# --- Основные функции ---

def write_raw_chunk(path_prefix: str, chunk_data: GenResult):
    """Сохраняет сырой чанк. Теперь ПРАВИЛЬНО работает с numpy-массивами."""
    meta_path = path_prefix + ".meta.json"
    grid_path = path_prefix + ".npz"

    meta = {
        "version": chunk_data.version, "type": chunk_data.type,
        "seed": chunk_data.seed, "cx": chunk_data.cx, "cz": chunk_data.cz,
        "size": chunk_data.size, "cell_size": chunk_data.cell_size,
        "stage_seeds": chunk_data.stage_seeds,
        "grid_spec": dataclasses.asdict(chunk_data.grid_spec) if chunk_data.grid_spec else None,
    }
    _atomic_write_json(meta_path, meta)

    height_grid = np.array(chunk_data.layers.get("height_q", {}).get("grid", []), dtype=np.float32)

    surface_ids = chunk_data.layers.get("surface")
    nav_ids = chunk_data.layers.get("navigation")

    if not isinstance(surface_ids, np.ndarray) or not isinstance(nav_ids, np.ndarray):
        print(
            f"!!! WARNING for chunk {chunk_data.cx},{chunk_data.cz}: Layers are not NumPy arrays! This may indicate a problem.")
        from ..constants import SURFACE_KIND_TO_ID, NAV_KIND_TO_ID
        surface_ids = np.array([[SURFACE_KIND_TO_ID.get(k, 0) for k in row] for row in surface_ids], dtype=np.uint8)
        nav_ids = np.array([[NAV_KIND_TO_ID.get(k, 1) for k in row] for row in nav_ids], dtype=np.uint8)

    _ensure_path_exists(grid_path)
    tmp_path = grid_path + ".tmp"
    with open(tmp_path, "wb") as f:
        np.savez_compressed(f, height=height_grid, surface=surface_ids.astype(np.uint8),
                            navigation=nav_ids.astype(np.uint8))

    # --- НАЧАЛО ИСПРАВЛЕНИЯ ---
    # Переименовываем временный файл в основной. Этого здесь не хватало.
    os.replace(tmp_path, grid_path)
    # --- КОНЕЦ ИСПРАВЛЕНИЯ ---


def read_raw_chunk(path_prefix: str) -> GenResult | None:
    """Читает сырой чанк. Теперь возвращает слои как numpy-массивы."""
    meta_path = path_prefix + ".meta.json"
    grid_path = path_prefix + ".npz"
    if not os.path.exists(meta_path) or not os.path.exists(grid_path):
        return None

    try:
        with open(meta_path, "r", encoding="utf-8") as f:
            meta = json.load(f)
        with np.load(grid_path) as data:
            height = data["height"].tolist()
            surface_ids = data["surface"]
            nav_ids = data["navigation"]

        spec = HexGridSpec(**meta["grid_spec"]) if meta.get("grid_spec") else None
        return GenResult(
            version=meta["version"], type=meta["type"], seed=meta["seed"],
            cx=meta["cx"], cz=meta["cz"], size=meta["size"],
            cell_size=meta["cell_size"], grid_spec=spec,
            stage_seeds=meta.get("stage_seeds", {}),
            layers={
                "height_q": {"grid": height},
                "surface": surface_ids,
                "navigation": nav_ids,
                "overlay": np.zeros((meta["size"], meta["size"]), dtype=np.int32),
            },
        )
    except Exception as e:
        print(f"!!! ERROR reading raw chunk {path_prefix}: {e}")
        return None


def write_raw_regional_layers(path: str, layers: Dict[str, np.ndarray], verbose: bool = False):
    """Сохраняет слои региона (климат и т.д.) в один сжатый NPZ файл."""
    _ensure_path_exists(path)
    tmp_path = path + ".tmp"
    try:
        with open(tmp_path, "wb") as f:
            np.savez_compressed(f, **layers)
        os.replace(tmp_path, path)
        if verbose: print(f"--- EXPORT: Raw regional layers saved to: {path}")
    except Exception as e:
        print(f"!!! LOG: CRITICAL ERROR while creating raw regional file {path}: {e}")