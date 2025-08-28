from typing import List

Grid = List[List[int]]

def get_neighbor_wall_count(grid: Grid, x: int, y: int, w: int, h: int) -> int:
    cnt = 0
    for j in range(y - 1, y + 2):
        for i in range(x - 1, x + 2):
            if i == x and j == y:
                continue
            if i < 0 or j < 0 or i >= w or j >= h:
                cnt += 1
            elif grid[j][i] == 1:
                cnt += 1
    return cnt

def make_noise_grid(rng, w: int, h: int, wall_chance: float) -> Grid:
    return [[1 if rng.random() < wall_chance else 0 for _ in range(w)] for _ in range(h)]

def smooth_cellular(grid: Grid, steps: int = 5) -> Grid:
    h, w = len(grid), len(grid[0])
    for _ in range(steps):
        newg = [[0] * w for _ in range(h)]
        for y in range(h):
            for x in range(w):
                n = get_neighbor_wall_count(grid, x, y, w, h)
                if grid[y][x] == 1:
                    newg[y][x] = 1 if n >= 4 else 0
                else:
                    newg[y][x] = 1 if n >= 5 else 0
        grid = newg
    return grid
