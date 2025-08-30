# engine/worldgen_core/base/export.py
from __future__ import annotations
import json

from typing import Any, Dict, List, Tuple, Union
from pathlib import Path
from ..utils.rle import encode_rle_rows, decode_rle_rows

try:
    from PIL import Image
    PIL_OK = True
except ImportError:
    PIL_OK = False

PREVIEW_TILE_PX = 2

# --------- main IO: chunk / meta / preview ---------

def write_chunk_rle_json(path: str,
                         kind_payload: Union[Dict[str, Any], List[List[Any]]],
                         size: int, seed: int, cx: int, cz: int) -> None:
    """
    Записывает chunk.rle.json.
    kind_payload может быть:
      - уже RLE: {"encoding":"rle_rows_v1","rows":[...]}
      - сырым гридом size×size (строки "ground"/"obstacle"/"water" или id).
    """
    # нормализуем в RLE
    if isinstance(kind_payload, dict) and kind_payload.get("encoding") == "rle_rows_v1":
        payload = kind_payload
    else:
        # считаем, что это сырая решётка
        if not isinstance(kind_payload, list):
            raise TypeError("kind_payload must be RLE dict or 2D list grid")
        payload = encode_rle_rows(kind_payload)

    chunk = {
        "encoding": "rle_rows_v1",
        "rows": payload.get("rows", []),
        "w": int(size),
        "h": int(size),
        "cx": int(cx),
        "cz": int(cz),
    }

    doc = {
        "version": "1.0",
        "type": "chunk",
        "seed": int(seed),
        "size": int(size),
        "chunk_size": int(size),
        "chunks": [chunk],
    }

    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)




def write_chunk_meta_json(path: str, meta: Dict[str, Any]) -> None:
    # ... (код этой функции без изменений) ...
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

def write_preview_png(path: str,
                      kind_payload: Union[Dict[str, Any], List[List[Any]]],
                      palette: Dict[str, str],
                      ports: Dict[str, List[int]] | Dict[str, Any] | None = None) -> None:
    """
    Рисуем превью PNG.
    """
    print(f"--- EXPORT: Попытка записи превью в: {path}")
    if not PIL_OK:
        print("!!! LOG: Библиотека Pillow не найдена, генерация превью пропущена.")
        return

    try:
        if isinstance(kind_payload, dict) and kind_payload.get("encoding") == "rle_rows_v1":
            grid = decode_rle_rows(kind_payload.get("rows", []))
        else:
            grid = kind_payload

        h = len(grid)
        w = len(grid[0]) if h else 0
        if w == 0 or h == 0:
            print("--- EXPORT: Предупреждение: пустая сетка для превью.")
            return

        ID2NAME = {0: "ground", 1: "obstacle", 2: "water", 3: "border", 4: "road"}

        def hex_to_rgb(s: str) -> Tuple[int, int, int]:
            s = s.lstrip("#")
            if len(s) == 3: s = "".join(c*2 for c in s)
            if len(s) != 6: return 0,0,0
            return int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16)

        def to_rgb(v: Any) -> Tuple[int, int, int]:
            name = v if isinstance(v, str) else ID2NAME.get(int(v), "ground")
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
        img.save(path, format="PNG")
        print(f"--- EXPORT: Превью успешно сохранено: {path}")

    except Exception as e:
        print(f"!!! LOG: КРИТИЧЕСКАЯ ОШИБКА при создании preview.png: {e}")