from __future__ import annotations
from typing import Any, Dict, List, Tuple
from ..base.generator import KIND_GROUND, KIND_OBSTACLE, KIND_WATER
from ..base.rng import RNG, edge_key
from ..grid_alg.features import fbm2d  # шум для hint/halo

# ---------- RLE ----------

def encode_rle_line(vals: List[int]) -> List[List[int]]:
    out: List[List[int]] = []
    if not vals:
        return out
    cur = int(vals[0]); run = 1
    for v in vals[1:]:
        v = int(v)
        if v == cur:
            run += 1
        else:
            out.append([cur, run]); cur = v; run = 1
    out.append([cur, run])
    return out

def encode_rle_rows(grid: List[List[int]]) -> Dict[str, Any]:
    return {"encoding": "rle_rows_v1", "rows": [encode_rle_line(row) for row in grid]}

# ---------- Кромка/порты ----------

def side_neighbor(cx: int, cz: int, side: str) -> Tuple[int, int]:
    if side == "N": return cx, cz - 1
    if side == "S": return cx, cz + 1
    if side == "W": return cx - 1, cz
    if side == "E": return cx + 1, cz
    raise ValueError(side)

def apply_border_ring(kind: List[List[str]], t: int) -> None:
    """Делаем непроходимую рамку толщиной t (окна портов прорежем отдельно)."""
    h = len(kind); w = len(kind[0]) if h else 0
    t = max(0, min(t, min(w, h)//2))
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
    """Точка внутри чанка сразу за рамкой — старт коридора."""
    if side == "N": return idx, t
    if side == "S": return idx, size - 1 - t
    if side == "W": return t, idx
    if side == "E": return size - 1 - t, idx
    raise ValueError(side)

def choose_ports(seed: int, cx: int, cz: int, size: int, cfg: Dict[str, Any]) -> Dict[str, List[int]]:
    """
    Детерминированный выбор сторон от edge_key + позиция окна.
    Соблюдаем min..max (2..4 по умолчанию).
    """
    pmin = int(cfg.get("min", 2)); pmax = int(cfg.get("max", 4))
    margin = int(cfg.get("edge_margin", 3))
    margin = max(0, min(margin, max(0, (size//2)-1)))

    sides = ["N","E","S","W"]
    active: Dict[str, bool] = {}
    pos: Dict[str, int] = {}

    for side in sides:
        nx, nz = side_neighbor(cx, cz, side)
        k = edge_key(seed, cx, cz, nx, nz)
        r = RNG(k)
        is_active = (r.u32() & 1) == 1
        idx = r.randint(margin, max(margin, size-1-margin)) if size > 0 else 0
        active[side] = is_active
        pos[side] = idx

    def count_active() -> int: return sum(1 for v in active.values() if v)
    # добираем до min
    if count_active() < pmin:
        for side in sides:
            if count_active() >= pmin: break
            nx, nz = side_neighbor(cx, cz, side)
            r = RNG(edge_key(seed, cx, cz, nx, nz)); _ = r.u32()
            if (r.u32() & 1) == 1: active[side] = True
    # урезаем до max
    if count_active() > pmax:
        for side in sides:
            if count_active() <= pmax: break
            nx, nz = side_neighbor(cx, cz, side)
            r = RNG(edge_key(seed, cx, cz, nx, nz)); _ = r.u32(); _ = r.u32()
            if (r.u32() & 1) == 1: active[side] = False

    return {s: ([] if not active[s] else [pos[s]]) for s in sides}

# ---------- Пути/коридоры ----------

def _step_cost(val: str) -> int:
    if val == KIND_GROUND:   return 1
    if val == KIND_OBSTACLE: return 8
    if val == KIND_WATER:    return 12
    return 1

def dijkstra_path(kind: List[List[str]], start: Tuple[int,int], goal: Tuple[int,int]) -> List[Tuple[int,int]]:
    import heapq
    h = len(kind); w = len(kind[0]) if h else 0
    sx, sz = start; gx, gz = goal
    dist = [[10**12 for _ in range(w)] for _ in range(h)]
    prev: List[List[Tuple[int,int] | None]] = [[None for _ in range(w)] for _ in range(h)]
    pq: List[Tuple[int,int,int]] = []
    dist[sz][sx] = 0
    heapq.heappush(pq, (0, sx, sz))
    while pq:
        d, x, z = heapq.heappop(pq)
        if (x, z) == (gx, gz): break
        if d != dist[z][x]: continue
        for dx, dz in ((1,0),(-1,0),(0,1),(0,-1)):
            nx, nz = x+dx, z+dz
            if 0 <= nx < w and 0 <= nz < h:
                nd = d + _step_cost(kind[nz][nx])
                if nd < dist[nz][nx]:
                    dist[nz][nx] = nd
                    prev[nz][nx] = (x, z)
                    heapq.heappush(pq, (nd, nx, nz))
    path: List[Tuple[int,int]] = []
    x, z = gx, gz
    if prev[z][x] is None and (x, z) != (sx, sz):
        return [start, goal]
    while True:
        path.append((x, z))
        if (x, z) == (sx, sz): break
        x, z = prev[z][x]
    path.reverse()
    return path

def carve_path(kind: List[List[str]], path: List[Tuple[int,int]], radius: int) -> None:
    if not path: return
    h = len(kind); w = len(kind[0]) if h else 0
    r = max(0, radius)
    for (x, z) in path:
        for dz in range(-r, r+1):
            for dx in range(-r, r+1):
                nx, nz = x+dx, z+dz
                if 0 <= nx < w and 0 <= nz < h:
                    kind[nz][nx] = KIND_GROUND

def carve_connectivity(kind: List[List[str]], points: List[Tuple[int,int]], width: int) -> None:
    if len(points) < 2: return
    pts = sorted(points, key=lambda p: (p[0]+p[1], p[0]))
    r = max(1, width // 2)
    for a, b in zip(pts[:-1], pts[1:]):
        path = dijkstra_path(kind, a, b)
        carve_path(kind, path, r)

# ---------- Hint/Halo и кромки ----------

def kind_to_id(v: str) -> int:
    return 0 if v == KIND_GROUND else (1 if v == KIND_OBSTACLE else 2)

def kind_to_pass(v: str) -> int:
    return 1 if v == KIND_GROUND else 0

def edges_tiles_and_pass_from_kind(kind: List[List[str]]) -> Dict[str, Any]:
    h = len(kind); w = len(kind[0]) if h else 0
    north = [kind[0][x]     for x in range(w)]
    south = [kind[h-1][x]   for x in range(w)]
    west  = [kind[z][0]     for z in range(h)]
    east  = [kind[z][w-1]   for z in range(h)]
    return {
        "N": {"tiles": encode_rle_line([kind_to_id(v) for v in north]),
              "pass":  encode_rle_line([kind_to_pass(v) for v in north])},
        "S": {"tiles": encode_rle_line([kind_to_id(v) for v in south]),
              "pass":  encode_rle_line([kind_to_pass(v) for v in south])},
        "W": {"tiles": encode_rle_line([kind_to_id(v) for v in west]),
              "pass":  encode_rle_line([kind_to_pass(v) for v in west])},
        "E": {"tiles": encode_rle_line([kind_to_id(v) for v in east]),
              "pass":  encode_rle_line([kind_to_pass(v) for v in east])},
    }

def compute_hint_and_halo(
    stage_seeds: Dict[str,int], cx: int, cz: int, size: int,
    obs_cfg: Dict[str, Any], wat_cfg: Dict[str, Any], halo_t: int
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """hint — одна линия сразу за границей; halo — t полос за границей."""
    od = float(obs_cfg.get("density", 0.12))
    ofreq = float(obs_cfg.get("freq", 1.0/28.0))
    ooct = int(obs_cfg.get("octaves", 3))
    wd = float(wat_cfg.get("density", 0.05))
    wfreq = float(wat_cfg.get("freq", 1.0/20.0))
    woct = int(wat_cfg.get("octaves", 3))

    def sample_kind(wx: int, wz: int) -> int:
        n_obs = fbm2d(stage_seeds["obstacles"], float(wx), float(wz), ofreq, octaves=ooct)
        n_w   = fbm2d(stage_seeds["water"],     float(wx), float(wz), wfreq,  octaves=woct)
        if n_w < wd: return 2
        return 1 if n_obs < od else 0

    top_wz    = cz*size - 1
    bottom_wz = cz*size + size
    left_wx   = cx*size - 1
    right_wx  = cx*size + size

    hint = {"N": {}, "S": {}, "W": {}, "E": {}}
    halo = {"N": {}, "S": {}, "W": {}, "E": {}}

    # N/S — по X, W/E — по Z
    n_line = [sample_kind(cx*size + x, top_wz) for x in range(size)]
    hint["N"] = encode_rle_rows([n_line])
    n_rows = [[sample_kind(cx*size + x, top_wz - r) for x in range(size)] for r in range(halo_t, 0, -1)]
    halo["N"] = encode_rle_rows(n_rows)

    s_line = [sample_kind(cx*size + x, bottom_wz) for x in range(size)]
    hint["S"] = encode_rle_rows([s_line])
    s_rows = [[sample_kind(cx*size + x, bottom_wz + r - 1) for x in range(size)] for r in range(1, halo_t+1)]
    halo["S"] = encode_rle_rows(s_rows)

    w_line = [sample_kind(left_wx, cz*size + z) for z in range(size)]
    hint["W"] = encode_rle_rows([[v] for v in w_line])
    w_rows = [[sample_kind(left_wx - r, cz*size + z) for z in range(size)] for r in range(halo_t, 0, -1)]
    halo["W"] = encode_rle_rows(w_rows)

    e_line = [sample_kind(right_wx, cz*size + z) for z in range(size)]
    hint["E"] = encode_rle_rows([[v] for v in e_line])
    e_rows = [[sample_kind(right_wx + r - 1, cz*size + z) for z in range(size)] for r in range(1, halo_t+1)]
    halo["E"] = encode_rle_rows(e_rows)

    return hint, halo
