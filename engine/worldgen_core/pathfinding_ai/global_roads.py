from __future__ import annotations
from typing import List, Tuple, Optional, Callable, Dict

from .road_helpers import Coord

def build_global_roads(
    load_chunk_fn: Callable[[int, int], Optional[Dict]],
    write_paths_fn: Callable[[int, int, List[List[Coord]]], None],
    center_cx: int, center_cz: int,
    radius_chunks: int,
    preset,
    params: Dict,
) -> None:
    """
    Заглушка под супер-чанковую прокладку.
    План:
      1) склеить окно (2R+1)×(2R+1) в единую сетку (kind/height),
      2) выбрать порты на внешней рамке и стыковки между чанками,
      3) маршрутизировать (A* через routers) и нарезать пути обратно по чанкам,
      4) вызвать write_paths_fn(cx,cz, paths_for_chunk).
    """
    return
