from typing import List, Dict

def tiles_flat(grid, y_level: int = 0) -> List[Dict]:
    """Плоский список тайлов для v0: [{x,z,y,tile} ...]."""
    h, w = len(grid), len(grid[0])
    out = []
    for y in range(h):
        for x in range(w):
            out.append({"x": x, "z": y, "y": y_level, "tile": grid[y][x]})
    return out
