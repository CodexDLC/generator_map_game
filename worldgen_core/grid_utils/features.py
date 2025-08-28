
from opensimplex import OpenSimplex
from .core import TILE, PASSABLE_DEFAULT
from .topology import bfs_reachable, neighbors4


def add_water(grid, seed: int, scale: float, thr: float) -> None:
    """Помечает часть пола как воду по шуму (OpenSimplex)."""
    h, w = len(grid), len(grid[0])
    noise = OpenSimplex(seed=seed ^ 0x1A2B3C4D)
    for y in range(h):
        for x in range(w):
            if grid[y][x] == TILE["FLOOR"]:
                v = noise.noise2(x / scale, y / scale)
                if (v + 1.0) * 0.5 > thr:
                    grid[y][x] = TILE["WATER"]

def pick_entry_exit(grid, rng):
    h, w = len(grid), len(grid[0])
    left  = [y for y in range(1, h-1) if grid[y][1] == TILE["FLOOR"]]
    right = [y for y in range(1, h-1) if grid[y][w-2] == TILE["FLOOR"]]
    ey = rng.choice(left) if left else h // 2

    # среди правых — сначала те, что достижимы от (1,ey)
    reach = [y for y in right if bfs_reachable(grid, (1, ey), (w-2, y), PASSABLE_DEFAULT, neighbors4)]
    if reach:
        xy = max(reach, key=lambda y: abs(y - ey))  # подальше по вертикали
    else:
        xy = (max(right, key=lambda y: abs(y - ey)) if right else h // 2)

    entry = (0, ey); exit_pos = (w-1, xy)
    grid[ey][0] = grid[ey][1] = TILE["FLOOR"]
    grid[xy][w-1] = grid[xy][w-2] = TILE["FLOOR"]
    return entry, exit_pos
