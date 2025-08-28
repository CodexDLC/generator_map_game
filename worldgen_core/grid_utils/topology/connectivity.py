from typing import List, Tuple, Set
from collections import deque
from .neighbors import neighbors4
from ..core import TILE
Grid = List[List[int]]

def largest_component_only(grid: Grid) -> None:
    w, h = len(grid[0]), len(grid)
    seen = [[False]*w for _ in range(h)]
    comps = []
    for y in range(h):
        for x in range(w):
            if grid[y][x] == TILE["FLOOR"] and not seen[y][x]:
                comp = []
                st = [(x,y)]; seen[y][x] = True
                while st:
                    px, py = st.pop(); comp.append((px,py))
                    for nx,ny in neighbors4(px,py,w,h):
                        if not seen[ny][nx] and grid[ny][nx] == TILE["FLOOR"]:
                            seen[ny][nx] = True; st.append((nx,ny))
                comps.append(comp)
    if not comps: return
    main = set(max(comps, key=len))
    for y in range(h):
        for x in range(w):
            if grid[y][x] == TILE["FLOOR"] and (x,y) not in main:
                grid[y][x] = TILE["WALL"]

def bfs_reachable(grid: Grid, start: Tuple[int,int], goal: Tuple[int,int], passable: Set[int]) -> bool:
    w, h = len(grid[0]), len(grid)
    sx,sy = start; gx,gy = goal
    if grid[sy][sx] not in passable or grid[gy][gx] not in passable: return False
    q = deque([start]); seen = {start}
    while q:
        x,y = q.popleft()
        if (x,y) == goal: return True
        for nx,ny in neighbors4(x,y,w,h):
            if grid[ny][nx] in passable and (nx,ny) not in seen:
                seen.add((nx,ny)); q.append((nx,ny))
    return False
