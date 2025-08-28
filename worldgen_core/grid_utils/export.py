from __future__ import annotations
import json
from pathlib import Path
from typing import Iterable

from PIL import Image, ImageDraw

from .core import PNG_COLORS


def _tiles_iter(grid: list[list[int]]) -> Iterable[dict]:
    h, w = len(grid), len(grid[0])
    for z in range(h):
        for x in range(w):
            yield {"x": x, "z": z, "y": 0, "tile": int(grid[z][x])}


def build_json_data(*, grid, params, entry, exit_pos, map_id, overlays=None, encoding="rle_rows_v1") -> dict:
    h, w = len(grid), len(grid[0])
    if encoding == "rle_rows_v1":
        chunk_payload = {"encoding": "rle_rows_v1", "rows": encode_rle_rows(grid)}
    else:
        # fallback: tiles_v0 (как раньше)
        tiles = [{"x": x, "z": z, "y": 0, "tile": int(grid[z][x])} for z in range(h) for x in range(w)]
        chunk_payload = {"encoding": "tiles_v0", "tiles": tiles}

    chunk = {"cx": 0, "cz": 0, "y": 0, "w": w, "h": h, **chunk_payload}
    if overlays:
        chunk["overlays"] = overlays

    return {
        "version": "1",
        "type": "grid",
        "map_id": map_id,
        "seed": params.seed,
        "cell_size": params.cell_size,
        "size": {"w": w, "h": h, "levels": params.levels},
        "chunk_size": params.chunk_size,
        "mode": getattr(params, "mode", "cave"),
        "tileset_map": {
            "0":"floor","1":"wall","2":"water_deep","3":"border",
            "4":"road","5":"grass","6":"forest","7":"mountain",
        },
        "entry": {"x": entry[0], "z": entry[1], "y": entry[2]},
        "exit":  None if exit_pos is None else {"x": exit_pos[0], "z": exit_pos[1], "y": exit_pos[2]},
        "chunks": [chunk],
    }


def save_json(
    data: dict,
    out_dir: Path,
    map_id: str,
    *,
    compact: bool = True,
    per_map_dir: bool = True,
    filename: str = "map.json",
) -> Path:
    out_dir = Path(out_dir)
    if per_map_dir:
        out_dir = out_dir / map_id
    out_dir.mkdir(parents=True, exist_ok=True)

    path = out_dir / filename  # например out/<map_id>/map.json
    with open(path, "w", encoding="utf-8") as f:
        if compact:
            json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
        else:
            json.dump(data, f, ensure_ascii=False, indent=2)
    return path


def render_png_preview(
    grid: list[list[int]],
    entry: tuple[int, int, int],
    exit_pos: tuple[int, int, int] | None,
    out_dir: Path,
    map_id: str,
    *,
    per_map_dir: bool = True,
    filename: str = "preview.png",
    tile_px: int = 12,
) -> Path:
    h, w = len(grid), len(grid[0])
    img = Image.new("RGB", (w * tile_px, h * tile_px), color="#000000")
    draw = ImageDraw.Draw(img)

    for z in range(h):
        for x in range(w):
            t = int(grid[z][x])
            col = PNG_COLORS.get(t, "#FF00FF")
            if col is None:
                continue
            x0, y0 = x * tile_px, z * tile_px
            x1, y1 = x0 + tile_px - 1, y0 + tile_px - 1
            draw.rectangle((x0, y0, x1, y1), fill=col)

    ex, ez, _ = entry
    draw.rectangle(
        (ex * tile_px, ez * tile_px, (ex + 1) * tile_px - 1, (ez + 1) * tile_px - 1),
        fill="#00AA00",
    )
    if exit_pos is not None:
        xx, xz, _ = exit_pos
        draw.rectangle(
            (xx * tile_px, xz * tile_px, (xx + 1) * tile_px - 1, (xz + 1) * tile_px - 1),
            fill="#CC0000",
        )

    target = (out_dir / map_id) if per_map_dir else out_dir
    target.mkdir(parents=True, exist_ok=True)
    p = target / filename
    img.save(p)
    return p


def encode_rle_rows(grid: list[list[int]]) -> list[list[list[int]]]:
    """grid[h][w] -> rows[z] = [[tile, run], ...]"""
    h, w = len(grid), len(grid[0])
    rows: list[list[list[int]]] = []
    for z in range(h):
        line = grid[z]
        if not line:
            rows.append([])
            continue
        cur_tile = line[0]
        run = 1
        out: list[list[int]] = []
        for x in range(1, w):
            t = line[x]
            if t == cur_tile:
                run += 1
            else:
                out.append([int(cur_tile), int(run)])
                cur_tile = t
                run = 1
        out.append([int(cur_tile), int(run)])
        rows.append(out)
    return rows

def decode_rle_rows(rows: list[list[list[int]]], w: int, h: int) -> list[list[int]]:
    """Обратно: rows -> grid[h][w]"""
    grid = [[0]*w for _ in range(h)]
    for z in range(h):
        x = 0
        for tile, run in rows[z]:
            for i in range(run):
                grid[z][x] = int(tile)
                x += 1
        if x != w:
            raise ValueError(f"RLE row {z}: sum(run)={x} != w={w}")
    if len(grid) != h:
        raise ValueError(f"RLE rows h={len(grid)} != {h}")
    return grid