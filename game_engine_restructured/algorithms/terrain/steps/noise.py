# ==============================================================================
# Файл: game_engine_restructured/algorithms/terrain/steps/noise.py
# ВЕРСИЯ 3.2: Базовый мировой шум -> всегда нормаль [0..1] без метров и гребней.
# ==============================================================================
from __future__ import annotations
from typing import Any, Dict
import numpy as np

from game_engine_restructured.core.utils.rng import hash64
from game_engine_restructured.numerics.fast_noise import fbm_grid_bipolar, fbm_amplitude

def _generate_noise_field(params: Dict[str, Any], context: Dict[str, Any]) -> np.ndarray:
    """
    Генерирует базовый FBM-шум и всегда возвращает нормализованный массив в диапазоне [0..1].
    Параметры, влияющие на форму: scale_tiles, octaves, gain, lacunarity.
    ridge/amp_m/shaping_power здесь игнорируются намеренно (глобальная "волна" без украшений).
    """
    x = context["x_coords"]
    z = context["z_coords"]
    cell_size = float(context["cell_size"])

    # Сид слоя из глобального сида и сдвига
    global_seed = int(context["seed"])
    seed_offset = int(params.get("seed_offset", 0))
    layer_seed = hash64(global_seed, seed_offset) & 0xFFFFFFFF

    gain       = float(params.get("gain", 0.5))
    octaves    = int(params.get("octaves", 4))
    lacunarity = float(params.get("lacunarity", 2.0))
    scale_tiles = float(params.get("scale_tiles", 1000.0))

    noise_params = {
        "seed": layer_seed,
        "coords_x": x,
        "coords_z": z,
        "freq0": 1.0 / (scale_tiles * cell_size + 1e-6),
        "octaves": octaves,
        "ridge": False,            # базовая волна мира — без гребней
        "gain": gain,
        "lacunarity": lacunarity,
    }

    # FBM в [-A..A], делим на аналитическую амплитуду -> [-1..1]
    raw = fbm_grid_bipolar(**noise_params).astype(np.float32, copy=False)
    max_amp = fbm_amplitude(gain, octaves)
    if max_amp > 1e-6:
        raw *= (1.0 / float(max_amp))

    # В [0..1] без террасирования/округления
    # clamp на всякий случай отбрасывает редко встречающиеся переполнения
    noise01 = (np.clip(raw, -1.0, 1.0) + 1.0) * 0.5
    return noise01.astype(np.float32, copy=False)
