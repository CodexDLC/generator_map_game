from __future__ import annotations
from typing import List, Tuple, Set, Dict, Callable
from math import inf
from heapq import heappush, heappop
from ..core import TILE
Grid = List[List[int]]
Pos = Tuple[int,int]

def a_star_generic(grid: Grid, start: Pos, goal: Pos,
                   step_cost: Callable[[int,int], float]) -> List[Pos] | None:
    H, W = len(grid), len(grid[0])
    sx,sy = start; gx,gy = goal
    def hfun(x:int,y:int)->int: return abs(x-gx)+abs(y-gy)
    g: Dict[Pos,float] = {(sx,sy): 0.0}
    parent: Dict[Pos,Pos] = {}
    pq: List[tuple[float,Pos]] = [(hfun(sx,sy), (sx,sy))]
    seen: Set[Pos] = set()
    while pq:
        _, (x,y) = heappop(pq)
        if (x,y) in seen: continue
        seen.add((x,y))
        if (x,y) == (gx,gy):
            path=[(x,y)]
            while (x,y) in parent:
                x,y = parent[(x,y)]; path.append((x,y))
            return list(reversed(path))
        for nx,ny in ((x+1,y),(x-1,y),(x,y+1),(x,y-1)):
            if not (0 <= nx < W and 0 <= ny < H): continue
            c = step_cost(nx,ny)
            if c == inf: continue
            ng = g[(x,y)] + c
            if ng < g.get((nx,ny), inf):
                g[(nx,ny)] = ng; parent[(nx,ny)] = (x,y)
                heappush(pq, (ng + hfun(nx,ny), (nx,ny)))
    return None

def a_star_abilities(grid: Grid, start: Pos, goal: Pos,
                     abilities: Set[str], rules: Dict[str,dict]) -> List[Pos] | None:
    name = {0:"floor",1:"wall",2:"water_deep",3:"border"}
    def step_cost(x:int,y:int)->float:
        t = grid[y][x]
        if t == TILE["BORDER"]: return inf
        r = rules.get(name.get(t,"unknown"), {})
        if r.get("base_passable", False):
            return float(r.get("move_cost", 1))
        req = set(r.get("requires_any", []))
        if req and (abilities & req):
            costs = [r.get("cost_with",{}).get(a,1) for a in abilities if a in r.get("cost_with",{})]
            return float(min(costs) if costs else 1)
        return inf
    return a_star_generic(grid, start, goal, step_cost)

def a_star_allow_walls(grid: Grid, start: Pos, goal: Pos, wall_cost: int = 4) -> List[Pos] | None:
    def step_cost(x:int,y:int)->float:
        t = grid[y][x]
        if t == TILE["BORDER"]: return inf
        return 1.0 if t == TILE["FLOOR"] else float(wall_cost)
    return a_star_generic(grid, start, goal, step_cost)

def carve_l(grid: Grid, a: Pos, b: Pos) -> None:
    (x0,y0),(x1,y1) = a,b
    sx = 1 if x1 >= x0 else -1
    sy = 1 if y1 >= y0 else -1
    for x in range(x0, x1+sx, sx): grid[y0][x] = TILE["FLOOR"]
    for y in range(y0, y1+sy, sy): grid[y][x1] = TILE["FLOOR"]

def carve_path_weighted(grid: Grid, start: Pos, goal: Pos,
                        width: int = 3, wall_cost: int = 4) -> List[Pos] | None:
    path = a_star_allow_walls(grid, start, goal, wall_cost)
    if path is None: return None
    k = max(0, (width-1)//2); H,W = len(grid), len(grid[0])
    for x,y in path:
        for dx in range(-k, k+1):
            for dy in range(-k, k+1):
                if abs(dx)+abs(dy) <= k:
                    nx,ny = x+dx, y+dy
                    if 0 <= nx < W and 0 <= ny < H:
                        grid[ny][nx] = TILE["FLOOR"]
        grid[y][x] = TILE["FLOOR"]
    return path
