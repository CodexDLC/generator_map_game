from typing import List
from ..core import TILE
Grid = List[List[int]]

def add_border(grid: Grid, mode: str = "cliff", outer_cells: int = 1) -> None:
    h, w = len(grid), len(grid[0])
    if mode == "void": return
    tile_code = TILE["BORDER"] if mode == "cliff" else TILE["WALL"]
    for k in range(outer_cells):
        for x in range(w):
            grid[0+k][x]   = tile_code
            grid[h-1-k][x] = tile_code
        for y in range(h):
            grid[y][0+k]   = tile_code
            grid[y][w-1-k] = tile_code
