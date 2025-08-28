from typing import List
from ..core import TILE
Grid = List[List[int]]

def _nb4(x:int,y:int,w:int,h:int):
    if x>0:    yield x-1,y
    if x<w-1:  yield x+1,y
    if y>0:    yield x,y-1
    if y<h-1:  yield x,y+1

def fill_small_voids(grid: Grid, max_area: int) -> None:
    """Меняет на FLOOR маленькие замкнутые области WALL, не касающиеся края."""
    H,W = len(grid), len(grid[0])
    seen = [[False]*W for _ in range(H)]
    for y in range(1,H-1):
        for x in range(1,W-1):
            if grid[y][x] != TILE["WALL"] or seen[y][x]: continue
            comp=[]; enclosed=True
            st=[(x,y)]; seen[y][x]=True
            while st:
                cx,cy = st.pop(); comp.append((cx,cy))
                if cx==0 or cy==0 or cx==W-1 or cy==H-1: enclosed=False
                for nx,ny in _nb4(cx,cy,W,H):
                    if not seen[ny][nx] and grid[ny][nx]==TILE["WALL"]:
                        seen[ny][nx]=True; st.append((nx,ny))
            if enclosed and len(comp) <= max_area:
                for cx,cy in comp: grid[cy][cx] = TILE["FLOOR"]

def widen_corridors(grid: Grid, iterations: int = 1) -> None:
    """Слегка утолщает проходы: WALL с ≥3 соседями FLOOR -> FLOOR."""
    H,W = len(grid), len(grid[0])
    for _ in range(iterations):
        to_floor=[]
        for y in range(H):
            for x in range(W):
                if grid[y][x] != TILE["WALL"]: continue
                n = 0
                for nx,ny in _nb4(x,y,W,H):
                    if grid[ny][nx] == TILE["FLOOR"]: n += 1
                if n >= 3: to_floor.append((x,y))
        for x,y in to_floor: grid[y][x] = TILE["FLOOR"]
