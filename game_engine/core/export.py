# game_engine/core/export.py
from __future__ import annotations
import json
import os
from typing import Any, Dict, List, Tuple, Union
from pathlib import Path

# --- ИЗМЕНЕНИЯ: Правильные пути ---
from .constants import ID_TO_KIND
from .utils.rle import encode_rle_rows, decode_rle_rows

try:
    from PIL import Image
    PIL_OK = True
except ImportError:
    PIL_OK = False

PREVIEW_TILE_PX = 2

def _atomic_write_json(path: str, data: Dict[str, Any]):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.rename(tmp_path, path)

def write_chunk_rle_json(path: str,
                         layers: Dict[str, Any],
                         size: int, seed: int, cx: int, cz: int) -> None:
    kind_payload = layers.get("kind", [])
    encoded_kind = encode_rle_rows(kind_payload)
    height_payload = layers.get("height_q", {}).get("grid", [])
    encoded_height = encode_rle_rows(height_payload)
    doc = {
        "version": "1.1", "type": "chunk_layers", "seed": int(seed),
        "size": int(size), "cx": int(cx), "cz": int(cz),
        "layers": {
            "kind": encoded_kind,
            "height_q": encoded_height,
        }
    }
    _atomic_write_json(path, doc)

def write_chunk_meta_json(path: str, meta: Dict[str, Any]) -> None:
    _atomic_write_json(path, meta)

def write_preview_png(path: str,
                      kind_payload: Union[Dict[str, Any], List[List[Any]]],
                      palette: Dict[str, str],
                      ports: Dict[str, Any] | None = None) -> None:
    if not PIL_OK:
        return
    try:
        grid = decode_rle_rows(kind_payload) if isinstance(kind_payload, dict) else kind_payload
        h = len(grid)
        w = len(grid[0]) if h else 0
        if w == 0 or h == 0:
            return

        def hex_to_rgb(s: str) -> Tuple[int, int, int]:
            s = s.lstrip("#")
            if len(s) == 3: s = "".join(c * 2 for c in s)
            if len(s) != 6: return 0, 0, 0
            return int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16)

        def to_rgb(v: Any) -> Tuple[int, int, int]:
            name = v if isinstance(v, str) else ID_TO_KIND.get(int(v), "ground")
            return hex_to_rgb(palette.get(name, "#000000"))

        img = Image.new("RGB", (w * PREVIEW_TILE_PX, h * PREVIEW_TILE_PX))
        px = img.load()

        for z in range(h):
            for x in range(w):
                color = to_rgb(grid[z][x])
                for dx in range(PREVIEW_TILE_PX):
                    for dy in range(PREVIEW_TILE_PX):
                        px[x * PREVIEW_TILE_PX + dx, z * PREVIEW_TILE_PX + dy] = color

        Path(path).parent.mkdir(parents=True, exist_ok=True)
        tmp_path = path + ".tmp"
        img.save(tmp_path, format="PNG")
        os.rename(tmp_path, path)
        print(f"--- EXPORT: Превью успешно сохранено: {path}")

    except Exception as e:
        print(f"!!! LOG: КРИТИЧЕСКАЯ ОШИБКА при создании preview.png: {e}")