
from __future__ import annotations
from typing import Any, Dict, List
import json

try:
    from PIL import Image
except Exception:
    Image = None

def _encode_rle_row(values: List[Any]) -> List[List[Any]]:
    out: List[List[Any]] = []
    if not values:
        return out
    cur = values[0]
    run = 1
    for v in values[1:]:
        if v == cur:
            run += 1
        else:
            out.append([cur, run])
            cur = v
            run = 1
    out.append([cur, run])
    return out

def encode_rle_rows(grid_2d: List[List[Any]]) -> Dict[str, Any]:
    return {"encoding": "rle_rows_v1", "rows": [_encode_rle_row(row) for row in grid_2d]}

def write_chunk_rle_json(path: str, header: Dict[str, Any], layers: Dict[str, Any], fields: Dict[str, Any], ports: Dict[str, List[int]], blocked: bool) -> None:
    payload: Dict[str, Any] = dict(header)
    enc_layers: Dict[str, Any] = {}

    kind_grid = layers.get("kind")
    if kind_grid is not None:
        enc_layers["kind"] = encode_rle_rows(kind_grid)

    hq = layers.get("height_q") or {}
    if hq and isinstance(hq, dict):
        grid = hq.get("grid")
        if grid is not None:
            enc_layers["height_q"] = {
                "zero": float(hq.get("zero", 0.0)),
                "scale": float(hq.get("scale", 0.1)),
                **encode_rle_rows(grid),
            }

    payload["layers"] = enc_layers

    enc_fields: Dict[str, Any] = {}
    for k in ("temperature_q", "humidity_q"):
        fq = fields.get(k) if isinstance(fields, dict) else None
        if fq and isinstance(fq, dict) and "grid" in fq:
            enc_fields[k] = {
                "zero": float(fq.get("zero", 0.0)),
                "scale": float(fq.get("scale", 1.0)),
                "downsample": int(fq.get("downsample", 1)),
                **encode_rle_rows(fq["grid"]),
            }
    if enc_fields:
        payload["fields"] = enc_fields

    payload["ports"] = ports
    payload["blocked"] = bool(blocked)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

def write_chunk_meta_json(path: str, header: Dict[str, Any], metrics: Dict[str, Any], stage_seeds: Dict[str, int], capabilities: Dict[str, Any]) -> None:
    payload = dict(header)
    payload["metrics"] = metrics
    payload["stage_seeds"] = stage_seeds
    payload["capabilities"] = capabilities
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

def write_preview_png(path: str, kind_grid: List[List[str]], palette: Dict[str, str], ports: Dict[str, List[int]] | None = None) -> None:
    if Image is None:
        # Pillow отсутствует — сохраняем JSON с палитрой как заглушку
        with open(path + ".txt", "w", encoding="utf-8") as f:
            json.dump({"note": "Pillow not installed, PNG skipped", "palette": palette}, f, ensure_ascii=False, indent=2)
        return
    h = len(kind_grid)
    w = len(kind_grid[0]) if h else 0
    img = Image.new("RGBA", (w, h))
    px = img.load()

    def parse_hex(c: str) -> tuple:
        c = c.lstrip("#")
        if len(c) == 6:
            r = int(c[0:2], 16); g = int(c[2:4], 16); b = int(c[4:6], 16); a = 255
        elif len(c) == 8:
            a = int(c[0:2], 16); r = int(c[2:4], 16); g = int(c[4:6], 16); b = int(c[6:8], 16)
        else:
            r=g=b=0; a=0
        return (r,g,b,a)

    for y in range(h):
        row = kind_grid[y]
        for x in range(w):
            col = palette.get(row[x], "#00000000")
            px[x, y] = parse_hex(col)

    # Нарисуем порты точками (красный)
    if ports:
        for side, arr in ports.items():
            if side == "N":
                y = 0
                for x in arr: 
                    if 0 <= x < w: px[x, y] = (255,0,0,255)
            elif side == "S":
                y = h - 1
                for x in arr:
                    if 0 <= x < w: px[x, y] = (255,0,0,255)
            elif side == "W":
                x = 0
                for y in arr:
                    if 0 <= y < h: px[x, y] = (255,0,0,255)
            elif side == "E":
                x = w - 1
                for y in arr:
                    if 0 <= y < h: px[x, y] = (255,0,0,255)

    img.save(path)
