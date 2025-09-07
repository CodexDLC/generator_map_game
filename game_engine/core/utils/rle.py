# Новое расположение: engine/worldgen_core/utils/rle.py

from __future__ import annotations
from typing import Any, Dict, List, Sequence


def encode_rle_line(line: Sequence[Any]) -> List[List[Any]]:
    """Кодирует одну строку в RLE формат."""
    out: List[List[Any]] = []
    if not line:
        return out
    cur = line[0]
    run = 1
    for v in line[1:]:
        if v == cur:
            run += 1
        else:
            out.append([cur, run])
            cur = v
            run = 1
    out.append([cur, run])
    return out


def encode_rle_rows(grid: List[List[Any]]) -> Dict[str, Any]:
    """Кодирует 2D-сетку в RLE формат по строкам."""
    return {"encoding": "rle_rows_v1", "rows": [encode_rle_line(row) for row in grid]}


def decode_rle_rows(rows: List[List[List[Any]]]) -> List[List[Any]]:
    """Декодирует RLE-строки обратно в 2D-сетку."""
    grid: List[List[Any]] = []
    for r in rows:
        line: List[Any] = []
        for val, run in r:
            line.extend([val] * int(run))
        grid.append(line)
    return grid
