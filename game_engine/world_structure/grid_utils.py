# game_engine/world_structure/grid_utils.py
from __future__ import annotations
from typing import Tuple


def region_key(cx: int, cz: int, region_size: int) -> Tuple[int, int]:
    """Calculates the region's unique key (scx, scz) from chunk coordinates."""
    offset = region_size // 2
    scx = (
        (cx + offset) // region_size if cx >= -offset else (cx - offset) // region_size
    )
    scz = (
        (cz + offset) // region_size if cz >= -offset else (cz - offset) // region_size
    )
    return scx, scz


def region_base(scx: int, scz: int, region_size: int) -> Tuple[int, int]:
    """Calculates the base chunk coordinates (cx, cz) of a region's top-left corner."""
    offset = region_size // 2
    base_cx = scx * region_size - offset
    base_cz = scz * region_size - offset
    return base_cx, base_cz
