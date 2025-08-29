from __future__ import annotations
import json
from typing import Any, Dict, List, Sequence, Tuple, Union
from pathlib import Path

# PIL опционально — превью делаем, если доступен
try:
    from PIL import Image
    PIL_OK = True
except Exception:
    PIL_OK = False


# ---------------- RLE helpers ----------------

def encode_rle_line(line: Sequence[Any]) -> List[List[Any]]:
    out: List[List[Any]] = []
    if not line:
        return out
    cur = line[0]; run = 1
    for v in line[1:]:
        if v == cur:
            run += 1
        else:
            out.append([cur, run])
            cur = v; run = 1
    out.append([cur, run])
    return out

def encode_rle_rows(grid: List[List[Any]]) -> Dict[str, Any]:
    return {"encoding": "rle_rows_v1", "rows": [encode_rle_line(row) for row in grid]}

def decode_rle_rows(rows: List[List[List[Any]]]) -> List[List[Any]]:
    grid: List[List[Any]] = []
    for r in rows:
        line: List[Any] = []
        for val, run in r:
            line.extend([val] * int(run))
        grid.append(line)
    return grid


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
    """
    Пишем meta как есть (ничего не навязываем). Главное — чтобы был json.
    """
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)


def write_preview_png(path: str,
                      kind_payload: Union[Dict[str, Any], List[List[Any]]],
                      palette: Dict[str, str],
                      ports: Dict[str, List[int]] | Dict[str, Any] | None = None) -> None:
    """
    Рисуем маленький превью PNG (по клетке = 1px).
    palette: {"ground":"#AABB77","obstacle":"#444", "water":"#2288ff", ...}
    """
    if not PIL_OK:
        return

    # получить грид значений (строки или id)
    if isinstance(kind_payload, dict) and kind_payload.get("encoding") == "rle_rows_v1":
        rows = kind_payload.get("rows", [])
        grid = decode_rle_rows(rows)
    else:
        grid = kind_payload  # предполагаем 2D список

    h = len(grid)
    w = len(grid[0]) if h else 0
    if w == 0 or h == 0:
        return

    # вспомогатели палитры: строка → rgb; числа мапим на имена
    # допустимые имена
    ID2NAME = {0: "ground", 1: "obstacle", 2: "water", 3: "border", 4: "road"}

    def hex_to_rgb(s: str) -> Tuple[int, int, int]:
        s = s.strip()
        if s.startswith("#"):
            s = s[1:]
        if len(s) == 3:
            s = "".join(ch*2 for ch in s)
        r = int(s[0:2], 16); g = int(s[2:4], 16); b = int(s[4:6], 16)
        return (r, g, b)

    def to_rgb(v: Any) -> Tuple[int, int, int]:
        if isinstance(v, str):
            name = v
        else:
            name = ID2NAME.get(int(v), "ground")
        col = palette.get(name, "#000000")
        return hex_to_rgb(col)

    img = Image.new("RGB", (w, h))
    px = img.load()
    for z in range(h):
        row = grid[z]
        for x in range(w):
            px[x, z] = to_rgb(row[x])

    Path(path).parent.mkdir(parents=True, exist_ok=True)
    img.save(path, format="PNG")
