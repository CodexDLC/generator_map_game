from typing import List, Set
Grid = List[List[int]]

def open_ratio(grid: Grid, passable: Set[int]) -> float:
    w, h = len(grid[0]), len(grid)
    open_cnt = sum(grid[y][x] in passable for y in range(h) for x in range(w))
    return open_cnt / (w*h)

def bump_open_to(grid: Grid, target: float, rng, passable: Set[int]) -> None:
    from .neighbors import neighbors4
    w, h = len(grid[0]), len(grid)
    cur = sum(grid[y][x] in passable for y in range(h) for x in range(w))
    need = max(0, int(target*w*h) - cur)
    if need == 0: return
    cand = [(x,y) for y in range(1,h-1) for x in range(1,w-1)
            if grid[y][x] == 1 and any(grid[ny][nx] in passable for nx,ny in neighbors4(x,y,w,h))]
    rng.shuffle(cand)
    for i in range(min(need, len(cand))):
        x,y = cand[i]; grid[y][x] = 0
