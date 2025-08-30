# engine/worldgen_core/grid_alg/features.py
from __future__ import annotations
from typing import List, Dict

from ..base.rng import RNG, hash64

# --------------------------- мировые шумы ---------------------------

def _val_at(seed: int, xi: int, zi: int) -> float:
    h = hash64(seed, xi, zi) & 0xFFFFFFFF
    return h / 0xFFFFFFFF

def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t

def _smoothstep(t: float) -> float:
    return t * t * (3.0 - 2.0 * t)

def value_noise2d(seed: int, x: float, z: float, freq: float) -> float:
    sx = x * freq
    sz = z * freq
    x0 = int(sx)
    z0 = int(sz)
    tx = _smoothstep(sx - x0)
    tz = _smoothstep(sz - z0)
    a = _val_at(seed, x0, z0)
    b = _val_at(seed, x0 + 1, z0)
    c = _val_at(seed, x0, z0 + 1)
    d = _val_at(seed, x0 + 1, z0 + 1)
    return _lerp(_lerp(a, b, tx), _lerp(c, d, tx), tz)

def fbm2d(seed: int, x: float, z: float, base_freq: float,
          octaves: int = 3, lacunarity: float = 2.0, gain: float = 0.5) -> float:
    amp = 1.0
    freq = base_freq
    total = 0.0
    norm = 0.0
    for _ in range(max(1, octaves)):
        total += value_noise2d(seed, x, z, freq) * amp
        norm += amp
        amp *= gain
        freq *= lacunarity
    return total / max(1e-9, norm)  # ~[0,1]

# --------------------------- маски ---------------------------

def _mask_from_noise(seed: int, cx: int, cz: int, size: int,
                     density: float, base_freq: float, octaves: int) -> List[List[int]]:
    """
    Бинарная маска size×size, 1 — заполнено. Порог ~= density (при равномерном распределении).
    Координаты мировые → швов нет.
    """
    grid = [[0 for _ in range(size)] for _ in range(size)]
    # защитим density на разумный диапазон
    d = max(0.0, min(1.0, float(density)))
    for z in range(size):
        wz = cz * size + z
        row = grid[z]
        for x in range(size):
            wx = cx * size + x
            n = fbm2d(seed, float(wx), float(wz), base_freq, octaves=octaves)
            # простое пороговое сравнение; при d=0.12 ожидаем ≈12% ячеек
            row[x] = 1 if n < d else 0
    return grid

def _ensure_nonempty_mask(mask: List[List[int]], rng: RNG, min_cells: int = 1) -> None:
    """Если маска оказалась пустой — рисуем одно компактное пятно, чтобы карта не была полностью 'ground'."""
    h = len(mask); w = len(mask[0]) if h else 0
    # посчитаем заполнение
    if sum(sum(r) for r in mask) >= min_cells:
        return
    cx = rng.randint(w // 4, max(w // 4, (3 * w) // 4))
    cz = rng.randint(h // 4, max(h // 4, (3 * h) // 4))
    rx = max(2, min(w // 6, 6))
    rz = max(2, min(h // 6, 6))
    for z in range(max(0, cz - rz), min(h, cz + rz + 1)):
        for x in range(max(0, cx - rx), min(w, cx + rx + 1)):
            dx = (x - cx) / float(rx)
            dz = (z - cz) / float(rz)
            if dx * dx + dz * dz <= 1.0:
                mask[z][x] = 1

def make_obstacles_world(seed: int, cx: int, cz: int, size: int, params: Dict) -> List[List[int]]:
    # дефолты частот подобраны под size≈64
    density = float(params.get("density", 0.12))
    freq = float(params.get("freq", 1.0 / 28.0))
    octaves = int(params.get("octaves", 3))
    mask = _mask_from_noise(seed ^ 0x55AA, cx, cz, size, density, freq, octaves)
    _ensure_nonempty_mask(mask, RNG(seed ^ 0xA5A5))
    return mask

def make_water_world(seed: int, cx: int, cz: int, size: int, params: Dict) -> List[List[int]]:
    density = float(params.get("density", 0.05))
    freq = float(params.get("freq", 1.0 / 20.0))
    octaves = int(params.get("octaves", 3))
    mask = _mask_from_noise(seed ^ 0x33CC, cx, cz, size, density, freq, octaves)
    # для воды fallback реже нужен, но пусть будет, чтобы точно не было 100% суши
    _ensure_nonempty_mask(mask, RNG(seed ^ 0xCC33))
    return mask

def merge_masks_into_kind(kind_grid: List[List[str]], obstacles: List[List[int]], water: List[List[int]]) -> None:
    h = len(kind_grid); w = len(kind_grid[0]) if h else 0
    for z in range(h):
        for x in range(w):
            if water[z][x]:
                kind_grid[z][x] = KIND_WATER
            elif obstacles[z][x]:
                kind_grid[z][x] = KIND_OBSTACLE
            else:
                kind_grid[z][x] = KIND_GROUND

def make_height_for_impassables(seed: int, cx: int, cz: int,
                                kind_grid: List[List[str]], scale: float,
                                base_freq: float = 1.0 / 16.0) -> List[List[int]]:
    """Высота только для непроходимых: мировая fbm, швов нет."""
    h = len(kind_grid); w = len(kind_grid[0]) if h else 0
    grid = [[0 for _ in range(w)] for _ in range(h)]
    for z in range(h):
        wz = cz * h + z
        row = grid[z]
        for x in range(w):
            if kind_grid[z][x] in (KIND_OBSTACLE, KIND_WATER):
                wx = cx * w + x
                n = fbm2d(seed, float(wx), float(wz), base_freq, octaves=4)
                row[x] = int(n * 65535)  # u16
            else:
                row[x] = 0
    return grid
