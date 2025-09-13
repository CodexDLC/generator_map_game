# ==============================================================================
# Файл: game_engine_restructured/core/export/binary_exporters.py
# Назначение: Функции для записи бинарных форматов (heightmap, controlmap).
# ==============================================================================
from __future__ import annotations
import os
from pathlib import Path
from typing import List

import numpy as np

from ..constants import SURFACE_ID_TO_KIND


def _ensure_path_exists(path: str) -> None:
    """Убеждается, что директория для файла существует."""
    Path(path).parent.mkdir(parents=True, exist_ok=True)


def _pack_control_data(base_id=0, overlay_id=0, blend=0, nav=True) -> np.uint32:
    val = 0
    val |= (base_id & 0x1F) << 27
    val |= (overlay_id & 0x1F) << 22
    val |= (blend & 0xFF) << 14
    if nav:
        val |= 1 << 3
    return np.uint32(val)


def write_heightmap_r16(
    path: str, height_grid: List[List[float]], max_height: float, verbose: bool = False
):
    """Сохраняет карту высот в 16-битном беззнаковом формате."""
    try:
        if not height_grid or not height_grid[0]:
            return
        if max_height <= 0:
            max_height = 1.0

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


def write_control_map_r32(
    path: str,
    surface_grid: np.ndarray,
    nav_grid: np.ndarray,
    overlay_grid: np.ndarray,
    verbose: bool = False,
):
    """Сохраняет управляющую карту текстур (control map) в 32-битном формате."""
    try:
        h, w = surface_grid.shape
        control_map = np.zeros((h, w), dtype="<u4")

        # Сбор статистики
        base_id_counts = {}
        overlay_id_counts = {}
        blend_counts = {}
        nav_counts = {True: 0, False: 0}

        for z in range(h):
            for x in range(w):
                base_id = int(surface_grid[z, x])  # Явное приведение к int
                is_navigable = nav_grid[z, x] in (0, 7)  # passable, bridge
                blend = 255 if overlay_grid[z, x] != 0 else 0
                overlay_id = int(overlay_grid[z, x])  # Явное приведение к int

                # Увеличение счетчиков
                base_id_counts[base_id] = base_id_counts.get(base_id, 0) + 1
                overlay_id_counts[overlay_id] = overlay_id_counts.get(overlay_id, 0) + 1
                blend_counts[blend] = blend_counts.get(blend, 0) + 1
                nav_counts[is_navigable] = nav_counts.get(is_navigable, 0) + 1

                control_map[z, x] = _pack_control_data(
                    base_id=base_id,
                    overlay_id=overlay_id,
                    blend=blend,
                    nav=is_navigable,
                )

        _ensure_path_exists(path)
        tmp_path = path + ".tmp"
        with open(tmp_path, "wb") as f:
            f.write(control_map.tobytes())
        os.replace(tmp_path, path)

        if verbose:
            from collections import Counter
            chunk_coords = Path(path).parent.name
            print(f"  -> [ControlMap] Stats for chunk {chunk_coords}:")
            for tile_id, count in sorted(base_id_counts.items()):
                tile_name = SURFACE_ID_TO_KIND.get(tile_id, f"Unknown_ID_{tile_id}")
                print(f"     - {tile_name}: {count} pixels")
            print(f"     - Overlay ID 0: {overlay_id_counts.get(0, 0)} pixels")
            print(f"     - Overlay ID > 0: {sum(v for k, v in overlay_id_counts.items() if k > 0)} pixels")
            print(f"     - Blend 0: {blend_counts.get(0, 0)} pixels")
            print(f"     - Blend 255: {blend_counts.get(255, 0)} pixels")
            print(f"     - Navigable: {nav_counts[True]} pixels")
            print(f"     - Non-navigable: {nav_counts[False]} pixels")
            print(f"--- EXPORT: Binary Control map (.r32) saved: {path}")

    except Exception as e:
        print(f"!!! LOG: CRITICAL ERROR while creating control.r32: {e}")