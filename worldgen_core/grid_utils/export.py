from pathlib import Path
from typing import Dict, Tuple
import uuid
import json
from PIL import Image, ImageDraw
from .core import PNG_COLORS, GenParams
from .io_pack import tiles_flat

def build_json(grid, entry: Tuple[int,int], exit_pos: Tuple[int,int],
               params: GenParams, map_id: str | None = None) -> Dict:
    h, w = len(grid), len(grid[0])
    if map_id is None:
        map_id = str(uuid.uuid4())

    tiles = tiles_flat(grid, y_level=0)
    data = {
        "version": "1",
        "map_id": map_id,
        "type": "grid",
        "seed": params.seed,
        "cell_size": params.cell_size,
        "size": {"w": w, "h": h, "levels": params.levels},
        "chunk_size": w,  # v0 = один чанк
        "tileset_map": {
            "0": "floor",
            "1": "wall",
            "2": "water"
        },
        "entry": {"x": entry[0], "z": entry[1], "y": 0},
        "exit":  {"x": exit_pos[0], "z": exit_pos[1], "y": 0},
        "chunks": [{
            "cx": 0, "cz": 0, "y": 0,
            "w": w, "h": h, "size": w,
            "encoding": "tiles_v0",
            "tiles": tiles
        }],
        "gen_params": {
            "wall_chance": params.wall_chance,
            "open_min": params.open_min,
            "water_scale": params.water_scale,
            "water_thr": params.water_thr
        }
    }
    return data

def save_json(data: Dict, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / f"{data['map_id']}.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    return json_path

def render_png(grid, entry: Tuple[int,int], exit_pos: Tuple[int,int],
               out_dir: Path, tile_px: int = 16, colors=PNG_COLORS) -> Path:
    h, w = len(grid), len(grid[0])
    out_dir.mkdir(parents=True, exist_ok=True)
    img = Image.new("RGB", (w * tile_px, h * tile_px), "black")
    draw = ImageDraw.Draw(img)
    for y in range(h):
        for x in range(w):
            t = grid[y][x]
            if t in colors:
                x0, y0 = x * tile_px, y * tile_px
                x1, y1 = x0 + tile_px - 1, y0 + tile_px - 1
                draw.rectangle([x0, y0, x1, y1], fill=colors[t])
    # вход/выход
    ex0, ey0 = entry
    draw.rectangle([ex0*tile_px, ey0*tile_px, (ex0+1)*tile_px-1, (ey0+1)*tile_px-1], fill="green")
    xx0, xy0 = exit_pos
    draw.rectangle([xx0*tile_px, xy0*tile_px, (xx0+1)*tile_px-1, (xy0+1)*tile_px-1], fill="red")

    # имя файла синхронно с JSON (без чтения JSON)
    map_id = uuid.uuid4().hex  # на уровне v0 можно отдельный id для PNG
    png_path = out_dir / f"{map_id}.png"
    img.save(png_path)
    return png_path
