# Замените ВСЁ содержимое файла game_engine/core/export.py на этот код:
from __future__ import annotations
import json
import os
from typing import Any, Dict, List, Tuple
from pathlib import Path
import dataclasses
import struct

# --- ИЗМЕНЕНИЕ: Добавляем импорт NumPy, если он есть ---
try:
    import numpy as np

    NUMPY_OK = True
except ImportError:
    NUMPY_OK = False

# --- ИЗМЕНЕНИЕ: Добавляем импорт Pillow (PIL) ---
try:
    from PIL import Image

    PIL_OK = True
except ImportError:
    PIL_OK = False

from ..world_structure.serialization import RegionMetaContract, ClientChunkContract
from .constants import ID_TO_KIND, KIND_TO_ID
from .utils.rle import encode_rle_rows


# --- (функции _atomic_write_json, write_region_meta, write_client_chunk, write_chunk_preview без изменений) ---
# Я привожу их здесь, чтобы можно было скопировать весь файл целиком.

def _atomic_write_json(path: str, data: Any):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path + ".tmp"

    def default_serializer(o):
        if dataclasses.is_dataclass(o):
            return dataclasses.asdict(o)
        raise TypeError(f"Object of type {type(o).__name__} is not JSON serializable")

    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=default_serializer)
    os.rename(tmp_path, path)


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
        h = len(kind_grid);
        w = len(kind_grid[0]) if h else 0
        if w == 0 or h == 0: return

        def hex_to_rgb(s: str) -> Tuple[int, int, int]:
            s = s.lstrip("#");
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
        tmp_path = path + ".tmp";
        img.save(tmp_path, format="PNG");
        os.rename(tmp_path, path)
    except Exception as e:
        print(f"!!! LOG: КРИТИЧЕСКАЯ ОШИБКА при создании preview.png: {e}")


# --- (твоя функция write_heightmap_r16, которую мы исправили в прошлый раз) ---
def write_heightmap_r16(path: str, height_grid: List[List[float]], max_height: float):
    """
    Нормализует высоты до диапазона [0.0, 1.0] и сохраняет их
    в бинарный файл как 16-битные float'ы (half-precision).
    """
    if not NUMPY_OK:
        print("!!! LOG: NumPy не найден, не могу сохранить .r16.")
        return
    try:
        if not height_grid or not height_grid[0]: return
        if max_height <= 0: max_height = 1.0

        height_array = np.array(height_grid, dtype=np.float32)
        # Нормализуем высоту, используя max_height из пресета
        normalized_array = np.clip(height_array / max_height, 0.0, 1.0)
        # Конвертируем в 16-битный float
        final_array = normalized_array.astype(np.float16)

        Path(path).parent.mkdir(parents=True, exist_ok=True)
        tmp_path = path + ".tmp"
        with open(tmp_path, 'wb') as f: f.write(final_array.tobytes())
        os.rename(tmp_path, path)
        print(f"--- EXPORT: 16-битная float-карта высот (нормализованная) сохранена: {path}")
    except Exception as e:
        print(f"!!! LOG: КРИТИЧЕСКАЯ ОШИБКА при создании heightmap.r16: {e}")


# --- НОВАЯ ФУНКЦИЯ ДЛЯ СОЗДАНИЯ COLOR MAP ---
def write_color_map_png(path: str, kind_grid: List[List[str]], palette: Dict[str, str]):
    """Генерирует colormap.png для чанка на основе палитры."""
    if not PIL_OK: return
    try:
        h = len(kind_grid)
        w = len(kind_grid[0]) if h > 0 else 0
        if w == 0 or h == 0: return

        def hex_to_rgb(s: str) -> Tuple[int, int, int]:
            s = s.lstrip("#")
            return int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16)

        img = Image.new("RGB", (w, h))
        px = img.load()
        for z in range(h):
            for x in range(w):
                kind = kind_grid[z][x]
                px[x, z] = hex_to_rgb(palette.get(kind, "#000000"))

        Path(path).parent.mkdir(parents=True, exist_ok=True)
        tmp_path = path + ".tmp"
        img.save(tmp_path, "PNG")
        os.rename(tmp_path, path)
        print(f"--- EXPORT: Color map сохранена: {path}")
    except Exception as e:
        print(f"!!! LOG: КРИТИЧЕСКАЯ ОШИБКА при создании colormap.png: {e}")


# --- НОВАЯ ФУНКЦИЯ ДЛЯ СОЗДАНИЯ CONTROL MAP ---
def write_control_map_png(path: str, kind_grid: List[List[str]]):
    """Генерирует control.png, распределяя типы по каналам RGBA."""
    if not PIL_OK: return
    try:
        h = len(kind_grid)
        w = len(kind_grid[0]) if h > 0 else 0
        if w == 0 or h == 0: return

        # Определяем, какой тип земли какому каналу соответствует.
        # R -> ground, G -> sand, B -> road/bridge, A -> slope
        # Это простой пример, можно сделать сложнее.
        CONTROL_MAPPING = {
            "ground": (255, 0, 0, 0),
            "sand": (0, 255, 0, 0),
            "road": (0, 0, 255, 0),
            "bridge": (0, 0, 255, 0),
            "slope": (0, 0, 0, 255),
        }
        DEFAULT_CONTROL = CONTROL_MAPPING["ground"]  # По умолчанию всё - земля

        img = Image.new("RGBA", (w, h))
        px = img.load()
        for z in range(h):
            for x in range(w):
                kind = kind_grid[z][x]
                px[x, z] = CONTROL_MAPPING.get(kind, DEFAULT_CONTROL)

        Path(path).parent.mkdir(parents=True, exist_ok=True)
        tmp_path = path + ".tmp"
        img.save(tmp_path, "PNG")
        os.rename(tmp_path, path)
        print(f"--- EXPORT: Control map сохранена: {path}")
    except Exception as e:
        print(f"!!! LOG: КРИТИЧЕСКАЯ ОШИБКА при создании control.png: {e}")