from typing import List, Tuple

from engine.worldgen_core.base.constants import KIND_OBSTACLE, KIND_GROUND


def side_neighbor(cx: int, cz: int, side: str) -> Tuple[int, int]:
    if side == "N": return cx, cz - 1
    if side == "S": return cx, cz + 1
    if side == "W": return cx - 1, cz
    if side == "E": return cx + 1, cz
    raise ValueError(side)

def apply_border_ring(kind: List[List[str]], t: int) -> None:
    """Делаем непроходимую рамку толщиной t (окна портов прорежем отдельно)."""
    h = len(kind)
    w = len(kind[0]) if h else 0
    t = max(0, min(t, min(w, h) // 2))
    if t == 0: return
    for z in range(h):
        for x in range(w):
            if z < t or z >= h - t or x < t or x >= w - t:
                kind[z][x] = KIND_OBSTACLE

def carve_port_window(kind: List[List[str]], side: str, idx: int, t: int, width: int) -> None:
    """Прорезаем окно шириной >=3 в рамке на стороне side, позиция idx вдоль стороны."""
    h = len(kind); w = len(kind[0]) if h else 0
    r = max(1, width // 2)
    if side == "N":
        for z in range(0, t):
            for x in range(max(0, idx - r), min(w, idx + r + 1)):
                kind[z][x] = KIND_GROUND
    elif side == "S":
        for z in range(h - t, h):
            for x in range(max(0, idx - r), min(w, idx + r + 1)):
                kind[z][x] = KIND_GROUND
    elif side == "W":
        for x in range(0, t):
            for z in range(max(0, idx - r), min(h, idx + r + 1)):
                kind[z][x] = KIND_GROUND
    elif side == "E":
        for x in range(w - t, w):
            for z in range(max(0, idx - r), min(h, idx + r + 1)):
                kind[z][x] = KIND_GROUND

def inner_point_for_side(side: str, idx: int, size: int, t: int) -> Tuple[int, int]:
    """Точка внутри Chunk сразу за рамкой — старт коридора."""
    if side == "N": return idx, t
    if side == "S": return idx, size - 1 - t
    if side == "W": return t, idx
    if side == "E": return size - 1 - t, idx
    raise ValueError(side)
# placeholders for future topology utilities
