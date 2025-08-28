from typing import List, Tuple, Set
from collections import deque
from .core import TILE

Grid = List[List[int]]

def neighbors4(x: int, y: int, w: int, h: int):
    for dx, dy in ((1,0), (-1,0), (0,1), (0,-1)):
        nx, ny = x + dx, y + dy
        if 0 <= nx < w and 0 <= ny < h:
            yield nx, ny

def open_ratio(grid: Grid, passable: Set[int]) -> float:
    w, h = len(grid[0]), len(grid)
    open_cnt = sum(grid[y][x] in passable for y in range(h) for x in range(w))
    return open_cnt / (w * h)

def bump_open_to(grid: Grid, target: float, rng, passable: Set[int]) -> None:
    """Открывает стены, примыкающие к проходимым клеткам, пока не достигнем цели."""
    w, h = len(grid[0]), len(grid)
    need = max(0, int(target * w * h) - sum(grid[y][x] in passable for y in range(h) for x in range(w)))
    if need == 0:
        return
    cand = [(x, y) for y in range(1, h-1) for x in range(1, w-1)
            if grid[y][x] == TILE["WALL"]
            and any(grid[ny][nx] in passable for nx, ny in neighbors4(x, y, w, h))]
    rng.shuffle(cand)
    for i in range(min(need, len(cand))):
        x, y = cand[i]
        grid[y][x] = TILE["FLOOR"]

def largest_component_only(grid: Grid) -> None:
    """Оставляет крупнейший компонент ПОЛА (только 0), остальное превращает в стены."""
    w, h = len(grid[0]), len(grid)
    seen = [[False]*w for _ in range(h)]
    comps = []
    for y in range(h):
        for x in range(w):
            if grid[y][x] == TILE["FLOOR"] and not seen[y][x]:
                comp = []
                st = [(x, y)]; seen[y][x] = True
                while st:
                    px, py = st.pop()
                    comp.append((px, py))
                    for nx, ny in neighbors4(px, py, w, h):
                        if not seen[ny][nx] and grid[ny][nx] == TILE["FLOOR"]:
                            seen[ny][nx] = True
                            st.append((nx, ny))
                comps.append(comp)
    if not comps:
        return
    comps.sort(key=len, reverse=True)
    main = set(comps[0])
    for y in range(h):
        for x in range(w):
            if grid[y][x] == TILE["FLOOR"] and (x, y) not in main:
                grid[y][x] = TILE["WALL"]

def add_border(grid: Grid) -> None:
    w, h = len(grid[0]), len(grid)
    for y in range(h):
        grid[y][0] = TILE["WALL"]
        grid[y][w-1] = TILE["WALL"]
    for x in range(w):
        grid[0][x] = TILE["WALL"]
        grid[h-1][x] = TILE["WALL"]

def bfs_reachable(grid, start, goal, passable, neighbors_fn=neighbors4):
    w, h = len(grid[0]), len(grid)
    sx, sy = start; gx, gy = goal
    if grid[sy][sx] not in passable or grid[gy][gx] not in passable:
        return False
    q = deque([start]); seen = {start}
    while q:
        x, y = q.popleft()
        if (x, y) == goal: return True
        for nx, ny in neighbors_fn(x, y, w, h):
            if grid[ny][nx] in passable and (nx, ny) not in seen:
                seen.add((nx, ny)); q.append((nx, ny))
    return False

def carve_l(grid: Grid, a: Tuple[int,int], b: Tuple[int,int]) -> None:
    (x0, y0), (x1, y1) = a, b
    step_x = 1 if x1 >= x0 else -1
    step_y = 1 if y1 >= y0 else -1
    for x in range(x0, x1 + step_x, step_x):
        grid[y0][x] = TILE["FLOOR"]
    for y in range(y0, y1 + step_y, step_y):
        grid[y][x1] = TILE["FLOOR"]



def neighbors8(x,y,w,h):
    for dx,dy in ((1,0),(-1,0),(0,1),(0,-1),(1,1),(1,-1),(-1,1),(-1,-1)):
        nx, ny = x+dx, y+dy
        if 0 <= nx < w and 0 <= ny < h:
            yield nx, ny
