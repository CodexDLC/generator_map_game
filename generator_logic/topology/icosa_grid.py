# ЗАМЕНА ВСЕГО ФАЙЛА: generator_logic/topology/icosa_grid.py
from __future__ import annotations
import math
from typing import List, Tuple, Dict
import numpy as np

EPS = 1e-12

def _icosahedron() -> Tuple[np.ndarray, np.ndarray]:
    phi = (1.0 + math.sqrt(5.0)) / 2.0
    verts = np.array([
        [-1, 0,  phi], [ 1, 0,  phi], [-1, 0, -phi], [ 1, 0, -phi],
        [0,  phi, -1], [0,  phi,  1], [0, -phi, -1], [0, -phi,  1],
        [ phi, -1, 0], [ phi,  1, 0], [-phi, -1, 0], [-phi,  1, 0]
    ], dtype=np.float64)

    faces = np.array([
        [0,11,5], [0,5,1], [0,1,7], [0,7,10], [0,10,11],
        [1,5,9], [5,11,4], [11,10,2], [10,7,6], [7,1,8],
        [3,9,4], [3,4,2], [3,2,6], [3,6,8], [3,8,9],
        [4,9,5], [2,4,11], [6,2,10], [8,6,7], [9,8,1]
    ], dtype=np.int32)

    return verts, faces

def _xyz_to_lonlat(X: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    x, y, z = X[:,0], X[:,1], X[:,2]
    lon = np.arctan2(y, x)
    lat = np.arcsin(np.clip(z, -1.0, 1.0))
    return lon, lat

def build_hexplanet(f: int, lon0_deg: float = 18.0) -> Dict[str, object]:
    if f < 1: raise ValueError("subdivision f must be >= 1")
    v0, F = _icosahedron()
    v_to_f = [[] for _ in range(12)]
    for face_idx, (v1, v2, v3) in enumerate(F):
        v_to_f[v1].append(face_idx)
        v_to_f[v2].append(face_idx)
        v_to_f[v3].append(face_idx)
    V, T, owner_face, local_xy = _subdivide_and_project(v0, F, f)
    neighbors = _vertex_adjacency_from_faces(T, V.shape[0])
    centers_xyz = _normalize(V).astype(np.float32)
    deg = np.array([len(nbs) for nbs in neighbors], dtype=np.int32)
    pent_ids = np.where(deg == 5)[0].astype(np.int32).tolist()
    hex_ids  = np.where(deg == 6)[0].astype(np.int32).tolist()
    N_cells = V.shape[0]
    lon, lat = _xyz_to_lonlat(centers_xyz)
    centers_lonlat_rad = np.stack([lon, lat], axis=1).astype(np.float32)
    cell_polys_lonlat_rad = _cell_polygons_lonlat(centers_xyz, T)
    RHOMB_PAIRS = [(0,1),(2,3),(4,5),(6,7),(8,9), (10,11),(12,13),(14,15),(16,17),(18,19)]
    FACE_ROT60 = {f:0 for f in range(20)}
    FACE_UPPER = {a:True for a,b in RHOMB_PAIRS} | {b:False for a,b in RHOMB_PAIRS}
    maps = {f: _face_affine(f, RHOMB_PAIRS, FACE_ROT60, FACE_UPPER) for f in range(20)}
    xy_net = np.zeros((V.shape[0], 2), dtype=np.float32)
    for vi in range(V.shape[0]):
        f_owner = owner_face[vi]
        if f_owner < 0: f_owner = v_to_f[vi][0]
        xloc, yloc = local_xy[vi]
        X, Y = maps[f_owner](xloc, yloc)
        xy_net[vi,0] = X; xy_net[vi,1] = Y
    minx,miny = xy_net[:,0].min(), xy_net[:,1].min()
    xy_net[:,0] -= minx; xy_net[:,1] -= miny
    maxx,maxy = xy_net[:,0].max(), xy_net[:,1].max()
    scale = max(maxx, maxy)
    if scale > 1e-6: xy_net /= scale
    return {
        "centers_xyz": centers_xyz, "centers_lonlat_rad": centers_lonlat_rad,
        "neighbors": neighbors, "pent_ids": pent_ids, "hex_ids": hex_ids,
        "lon0_rad": math.radians(lon0_deg), "cell_polys_lonlat_rad": cell_polys_lonlat_rad,
        "triangles": T, "net_xy01": xy_net.astype(np.float32)
    }

def _face_affine(face_id, RHOMB_PAIRS, FACE_ROT60, FACE_UPPER):
    rot = FACE_ROT60.get(face_id, 0)
    upper = FACE_UPPER[face_id]
    col, row = 0, 0
    for idx,(fa,fb) in enumerate(RHOMB_PAIRS):
        if face_id in (fa,fb): col = idx % 5; row = idx // 5; break
    ox = col * 1.5
    oy = row * math.sqrt(3)
    def map_point(x,y):
        cx, cy = (0.5, math.sqrt(3)/4.0)
        dx, dy = (x - cx, y - cy)
        ang = rot * (math.pi/3.0)
        rx =  dx*math.cos(ang) - dy*math.sin(ang)
        ry =  dx*math.sin(ang) + dy*math.cos(ang)
        X = rx + cx + ox
        Y = (ry + cy + oy) if upper else (ry + cy + oy - math.sqrt(3)/2.0)
        return X, Y
    return map_point

def _normalize(V: np.ndarray) -> np.ndarray:
    n = np.linalg.norm(V, axis=1, keepdims=True)
    n[n < EPS] = 1.0
    return V / n

def _subdivide_and_project(V0: np.ndarray, F: np.ndarray, f: int) -> Tuple[np.ndarray, np.ndarray, List[int], List[Tuple[float,float]]]:
    V0 = _normalize(V0.copy())
    verts: List[List[float]] = V0.tolist()
    faces_out: List[Tuple[int,int,int]] = []
    owner_face = [-1] * 12
    local_xy   = [(0.0, 0.0)] * 12
    A2 = np.array([0.0, 0.0]); B2 = np.array([1.0, 0.0]); C2 = np.array([0.5, math.sqrt(3)/2.0])
    edge_cache: Dict[Tuple[int,int,int,int], int] = {}
    def get_edge_point(a: int, b: int, step: int, which: str, face_id: int) -> int:
        if step <= 0: return a
        if step >= f: return b
        if a < b: key = (a, b, step, f); t = step / float(f); pa, pb = a, b
        else: key = (b, a, f - step, f); t = (f - step) / float(f); pa, pb = b, a
        idx = edge_cache.get(key, -1)
        if idx != -1: return idx
        A = V0[pa]; B = V0[pb]
        p = (1.0 - t) * A + t * B
        p = p / (np.linalg.norm(p) + EPS)
        idx = len(verts)
        verts.append(p.tolist())
        if which == 'AB': P2 = (1-t)*A2 + t*B2
        elif which == 'AC': P2 = (1-t)*A2 + t*C2
        else: P2 = (1-t)*B2 + t*C2
        owner_face.append(face_id)
        local_xy.append((float(P2[0]), float(P2[1])))
        edge_cache[key] = idx
        return idx
    for face_id, (a, b, c) in enumerate(F):
        def edge_AB_point(step): return get_edge_point(a, b, step, which='AB', face_id=face_id)
        def edge_AC_point(step): return get_edge_point(a, c, step, which='AC', face_id=face_id)
        def edge_BC_point(step): return get_edge_point(c, b, step, which='BC', face_id=face_id)
        grid: List[List[int]] = []
        for i in range(f + 1):
            row: List[int] = []
            max_j = f - i
            for j in range(max_j + 1):
                k = f - i - j
                if i == f and j == 0: idx = a
                elif j == f and i == 0: idx = b
                elif k == f and i == 0 and j == 0: idx = c
                elif k == 0: idx = edge_AB_point(j)
                elif j == 0: idx = edge_AC_point(f - i)
                elif i == 0: idx = edge_BC_point(j)
                else:
                    A = V0[a]; B = V0[b]; C = V0[c]
                    p = (i * A + j * B + k * C) / float(f)
                    p = p / (np.linalg.norm(p) + EPS)
                    idx = len(verts)
                    verts.append(p.tolist())
                    P2 = (i*A2 + j*B2 + k*C2) / float(f)
                    owner_face.append(face_id)
                    local_xy.append((float(P2[0]), float(P2[1])))
                row.append(idx)
            grid.append(row)
        for i in range(f):
            max_j = f - i
            for j in range(max_j):
                v00 = grid[i][j]; v10 = grid[i + 1][j]; v01 = grid[i][j + 1]
                faces_out.append((v00, v10, v01))
                if j < max_j - 1: v11 = grid[i + 1][j + 1]; faces_out.append((v10, v11, v01))
    V = np.asarray(verts, dtype=np.float64)
    V = _normalize(V)
    T = np.asarray(faces_out, dtype=np.int32)
    return V, T, owner_face, local_xy

def _vertex_adjacency_from_faces(T: np.ndarray, nV: int) -> List[List[int]]:
    adj: List[set] = [set() for _ in range(nV)]
    for a, b, c in T:
        adj[a].add(b); adj[a].add(c)
        adj[b].add(a); adj[b].add(c)
        adj[c].add(a); adj[c].add(b)
    return [sorted(list(s)) for s in adj]

def _tangent_basis(n: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    a = np.array([1.0, 0.0, 0.0], dtype=np.float64)
    if abs(float(n @ a)) > 0.9: a = np.array([0.0, 1.0, 0.0], dtype=np.float64)
    t = a - n * float(n @ a)
    t /= (np.linalg.norm(t) + 1e-12)
    b = np.cross(n, t)
    b /= (np.linalg.norm(b) + 1e-12)
    return t, b

def _triangle_centroids_xyz(V: np.ndarray, T: np.ndarray) -> np.ndarray:
    C = V[T[:,0]] + V[T[:,1]] + V[T[:,2]]
    return C / (np.linalg.norm(C, axis=1, keepdims=True) + 1e-12)

def _incident_faces(T: np.ndarray, nV: int) -> list[list[int]]:
    inc = [[] for _ in range(nV)]
    for fi, (a,b,c) in enumerate(T):
        inc[a].append(fi); inc[b].append(fi); inc[c].append(fi)
    return inc

def _cell_polygons_lonlat(V: np.ndarray, T: np.ndarray) -> list[np.ndarray]:
    C = _triangle_centroids_xyz(V, T)
    inc = _incident_faces(T, V.shape[0])
    polys = []
    for v_idx in range(V.shape[0]):
        n = V[v_idx]
        t, b = _tangent_basis(n)
        fids = inc[v_idx]
        if not fids: polys.append(np.zeros((0,2), dtype=np.float32)); continue
        angles = []
        for fi in fids:
            q = C[fi]
            w = q - n * float(n @ q)
            wx = float(w @ t); wy = float(w @ b)
            ang = math.atan2(wy, wx)
            angles.append((ang, fi))
        angles.sort(key=lambda x: x[0])
        ring = np.array([C[fi] for (ang, fi) in angles], dtype=np.float64)
        lon, lat = _xyz_to_lonlat(ring)
        polys.append(np.stack([lon, lat], axis=1).astype(np.float32))
    return polys

def lonlat_to_uv(lon_rad: float, lat_rad: float, lon0_rad: float) -> Tuple[float, float]:
    u = (lon_rad - lon0_rad) / (2.0 * math.pi)
    u = u - math.floor(u)
    v = (lat_rad + math.pi * 0.5) / math.pi
    return u, v

def uv_to_lonlat(u: float, v: float, lon0_rad: float) -> Tuple[float, float]:
    lon = lon0_rad + u * (2.0 * math.pi)
    lon = ((lon + math.pi) % (2.0 * math.pi)) - math.pi
    lat = v * math.pi - math.pi * 0.5
    return lon, lat

def nearest_cell_by_lonlat(lon_rad: float, lat_rad: float, centers_lonlat_rad: np.ndarray) -> int:
    dlon = centers_lonlat_rad[:,0] - lon_rad
    dlon = (dlon + math.pi) % (2.0 * math.pi) - math.pi
    dlat = centers_lonlat_rad[:,1] - lat_rad
    dist2 = dlon * dlon + dlat * dlat
    return int(np.argmin(dist2))

def nearest_cell_by_xyz(p_xyz: np.ndarray, centers_xyz: np.ndarray) -> int:
    dot_products = np.dot(centers_xyz, p_xyz)
    return int(np.argmax(dot_products))