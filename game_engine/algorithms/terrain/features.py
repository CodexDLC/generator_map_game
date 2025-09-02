# game_engine/algorithms/terrain/features.py
from __future__ import annotations
from typing import List

from opensimplex import OpenSimplex

# --- ИЗМЕНЕНИЯ: Правильные пути ---
from ...core.utils.rng import hash64, RNG


def _val_at(seed: int, xi: int, zi: int) -> float:
    h = hash64(seed, xi, zi) & 0xFFFFFFFF
    return h / 0xFFFFFFFF


def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def _smoothstep(t: float) -> float:
    return t * t * (3.0 - 2.0 * t)

def fbm2d(noise: OpenSimplex, x: float, z: float, base_freq: float,
          octaves: int = 3, lacunarity: float = 2.0, gain: float = 0.5) -> float:
    amp = 1.0
    freq = base_freq
    total = 0.0
    norm = 0.0

    for _ in range(max(1, octaves)):
        sample = (noise.noise2(x * freq, z * freq) + 1.0) / 2.0
        total += sample * amp
        norm += amp
        amp *= gain
        freq *= lacunarity

    return total / max(1e-9, norm)

def _mask_from_noise(seed: int, cx: int, cz: int, size: int,
                     density: float, base_freq: float, octaves: int) -> List[List[int]]:
    grid = [[0 for _ in range(size)] for _ in range(size)]
    d = max(0.0, min(1.0, float(density)))
    noise_gen = OpenSimplex(seed)
    for z in range(size):
        wz = cz * size + z
        row = grid[z]
        for x in range(size):
            wx = cx * size + x
            n = fbm2d(noise_gen, float(wx), float(wz), base_freq, octaves=octaves)
            row[x] = 1 if n < d else 0
    return grid


def _ensure_nonempty_mask(mask: List[List[int]], rng: RNG, min_cells: int = 1) -> None:
    h = len(mask)
    w = len(mask[0]) if h else 0
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