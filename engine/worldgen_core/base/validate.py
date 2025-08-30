
from __future__ import annotations
from typing import Any, Dict, List

from engine.worldgen_core.base.constants import KIND_VALUES, KIND_GROUND, KIND_OBSTACLE, KIND_WATER


def validate_rle_rows(size: int, rle_obj: Dict[str, Any]) -> None:
    if not isinstance(rle_obj, dict) or rle_obj.get("encoding") != "rle_rows_v1":
        raise ValueError("RLE object must have encoding='rle_rows_v1'")
    rows = rle_obj.get("rows")
    if not isinstance(rows, list) or len(rows) != size:
        raise ValueError("RLE rows must be a list with length=size")
    for i, row in enumerate(rows):
        if not isinstance(row, list):
            raise ValueError(f"RLE row {i} must be a list")
        total = 0
        for pair in row:
            if not (isinstance(pair, list) and len(pair) == 2):
                raise ValueError(f"RLE row {i} pair must be [value, run]")
            run = pair[1]
            if not isinstance(run, int) or run <= 0:
                raise ValueError(f"RLE row {i} run must be positive int")
            total += run
        if total != size:
            raise ValueError(f"RLE row {i} total run {total} != size {size}")

def validate_ports(size: int, ports: Dict[str, List[int]]) -> None:
    for side in ("N","E","S","W"):
        arr = ports.get(side, [])
        if not isinstance(arr, list):
            raise ValueError(f"ports[{side}] must be list")
        for v in arr:
            if not isinstance(v, int):
                raise ValueError(f"ports[{side}] value must be int")
            if not (0 <= v < size):
                raise ValueError(f"ports[{side}] index {v} out of range 0..{size-1}")

def compute_metrics(kind_grid: List[List[str]]) -> Dict[str, float]:
    h = len(kind_grid); w = len(kind_grid[0]) if h else 0
    total = h*w if h else 0
    if total == 0: return {"open_pct":0.0,"obstacle_pct":0.0,"water_pct":0.0}
    counts = {k:0 for k in KIND_VALUES}
    for row in kind_grid:
        for v in row:
            counts[v] = counts.get(v,0)+1
    open_cells = counts.get(KIND_GROUND,0)
    obstacle_cells = counts.get(KIND_OBSTACLE,0)
    water_cells = counts.get(KIND_WATER,0)
    return {
        "open_pct": open_cells/total,
        "obstacle_pct": obstacle_cells/total,
        "water_pct": water_cells/total,
    }

def validate_chunk_contract(header: Dict[str, Any], layers: Dict[str, Any], fields: Dict[str, Any], ports: Dict[str, Any]) -> None:
    size = int(header.get("size", 0))
    if size < 8:
        raise ValueError("size must be >= 8")
    for key in ("version","type","seed","cx","cz","cell_size"):
        if key not in header:
            raise ValueError(f"header missing {key}")
    # kind
    kind = layers.get("kind")
    if not isinstance(kind, list) or len(kind) != size or any(len(r)!=size for r in kind):
        raise ValueError("layers.kind must be a size×size grid (list of lists)")
    for row in kind:
        for v in row:
            if v not in KIND_VALUES:
                raise ValueError(f"layers.kind contains unknown value {v}")
    # height_q
    hq = layers.get("height_q")
    if not isinstance(hq, dict) or "grid" not in hq:
        raise ValueError("layers.height_q must be a dict with 'grid'")
    hgrid = hq["grid"]
    if not isinstance(hgrid, list) or len(hgrid) != size or any(len(r)!=size for r in hgrid):
        raise ValueError("height_q.grid must be size×size grid")
    # ports
    validate_ports(size, ports)
