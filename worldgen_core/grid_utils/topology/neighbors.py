from typing import Iterator

def neighbors4(x: int, y: int, w: int, h: int) -> Iterator[tuple[int,int]]:
    for dx, dy in ((1,0),(-1,0),(0,1),(0,-1)):
        nx, ny = x+dx, y+dy
        if 0 <= nx < w and 0 <= ny < h:
            yield nx, ny

def neighbors8(x: int, y: int, w: int, h: int) -> Iterator[tuple[int,int]]:
    for dx,dy in ((1,0),(-1,0),(0,1),(0,-1),(1,1),(1,-1),(-1,1),(-1,-1)):
        nx, ny = x+dx, y+dy
        if 0 <= nx < w and 0 <= ny < h:
            yield nx, ny
