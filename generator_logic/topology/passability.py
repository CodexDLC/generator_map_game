# generator_logic/topology/passability.py
from __future__ import annotations
from typing import List
import numpy as np

def build_passability_flags(neighbors: List[List[int]], pent_ids: list[int], buffer_hops: int = 1):
    N = len(neighbors)
    passable = np.ones(N, dtype=bool)
    blocked = set(int(i) for i in pent_ids)
    frontier = set(blocked)
    for _ in range(max(0, int(buffer_hops))):
        new_frontier = set()
        for v in frontier:
            for u in neighbors[v]:
                if u not in blocked:
                    blocked.add(u)
                    new_frontier.add(u)
        frontier = new_frontier
    passable[list(blocked)] = False
    return passable
