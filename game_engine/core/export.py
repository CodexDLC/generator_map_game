# ПЕРЕПИШИТЕ ФАЙЛ: game_engine/core/export.py
from __future__ import annotations
import json
import os
from typing import Any, Dict, List, Tuple
from pathlib import Path
import dataclasses

from ..world_structure.serialization import RegionMetaContract, ClientChunkContract
from .constants import ID_TO_KIND, KIND_TO_ID
from .utils.rle import encode_rle_rows, \
    decode_rle_rows


try:
    from PIL import Image

    PIL_OK = True
except ImportError:
    PIL_OK = False

PREVIEW_TILE_PX = 2


def _atomic_write_json(path: str, data: Any):
    """Атомарная запись JSON с поддержкой dataclass и кортежей в ключах."""
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path + ".tmp"

    def default_serializer(o):
        if dataclasses.is_dataclass(o):
            return dataclasses.asdict(o)
        if isinstance(o, tuple):
            return f"__tuple__{list(o)}"
        raise TypeError(f"Object of type {type(o).__name__} is not JSON serializable")

    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=default_serializer)
    os.rename(tmp_path, path)


def write_region_meta(path: str, meta_contract: RegionMetaContract):
    """Сохраняет метаданные региона."""
    _atomic_write_json(path, meta_contract)
    print(f"--- EXPORT: Метаданные региона сохранены: {path}")


# --- ИСПРАВЛЕННАЯ ВЕРСИЯ ФУНКЦИИ ---
def write_client_chunk(path: str, chunk_contract: ClientChunkContract):
    """
    Сохраняет готовый чанк для клиента, ПРАВИЛЬНО кодируя слои в RLE.
    """
    output_data = {
        "version": chunk_contract.version,
        "cx": chunk_contract.cx,
        "cz": chunk_contract.cz,
        "layers": {}
    }

    for layer_name, grid_data in chunk_contract.layers.items():
        if layer_name == "kind":
            # Для 'kind' заменяем строки на ID для экономии места
            id_grid = [[KIND_TO_ID.get(kind, 4) for kind in row] for row in grid_data]
            output_data["layers"][layer_name] = encode_rle_rows(id_grid)
        elif layer_name == "height_q" and isinstance(grid_data, dict) and "grid" in grid_data:
            # Для 'height_q' берем вложенный грид
            output_data["layers"][layer_name] = encode_rle_rows(grid_data["grid"])

    _atomic_write_json(path, output_data)


def write_chunk_preview(path: str, kind_grid: List[List[Any]], palette: Dict[str, str]):
    """Генерирует preview.png для чанка."""
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

        img = Image.new("RGB", (w * PREVIEW_TILE_PX, h * PREVIEW_TILE_PX))
        px = img.load()

        for z in range(h):
            for x in range(w):
                color = to_rgb(kind_grid[z][x])
                for dx in range(PREVIEW_TILE_PX):
                    for dy in range(PREVIEW_TILE_PX):
                        px[x * PREVIEW_TILE_PX + dx, z * PREVIEW_TILE_PX + dy] = color

        Path(path).parent.mkdir(parents=True, exist_ok=True)
        tmp_path = path + ".tmp"
        img.save(tmp_path, format="PNG")
        os.rename(tmp_path, path)
    except Exception as e:
        print(f"!!! LOG: КРИТИЧЕСКАЯ ОШИБКА при создании preview.png: {e}")