# NEW FILE: game_engine/world_structure/grid_utils.py
from __future__ import annotations
from typing import Tuple

# --- All grid-related constants and functions now live here ---

REGION_SIZE = 5
REGION_OFFSET = REGION_SIZE // 2

def region_key(cx: int, cz: int) -> Tuple[int, int]:
    """Calculates the region's unique key (scx, scz) from chunk coordinates."""
    scx = (cx + REGION_OFFSET) // REGION_SIZE if cx >= -REGION_OFFSET else (cx - REGION_OFFSET) // REGION_SIZE
    scz = (cz + REGION_OFFSET) // REGION_SIZE if cz >= -REGION_OFFSET else (cz - REGION_OFFSET) // REGION_SIZE
    return scx, scz

def region_base(scx: int, scz: int) -> Tuple[int, int]:
    """Calculates the base chunk coordinates (cx, cz) of a region's top-left corner."""
    base_cx = scx * REGION_SIZE - REGION_OFFSET
    base_cz = scz * REGION_SIZE - REGION_OFFSET
    return base_cx, base_cz