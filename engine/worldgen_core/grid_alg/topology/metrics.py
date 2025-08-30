# engine/worldgen_core/grid_alg/topology/metrics.py
from __future__ import annotations
from typing import Any, Dict, List, Tuple

from engine.worldgen_core.grid_alg.features import fbm2d
from engine.worldgen_core.utils.rle import encode_rle_rows, encode_rle_line


# --- Вспомогательные функции, которые мы перенесли раньше ---

def kind_to_id(v: str) -> int:
    return 0 if v == "ground" else (1 if v == "obstacle" else 2)


def kind_to_pass(v: str) -> int:
    return 1 if v == "ground" else 0


def edges_tiles_and_pass_from_kind(kind: List[List[str]]) -> Dict[str, Any]:
    h = len(kind)
    w = len(kind[0]) if h else 0
    north = [kind[0][x] for x in range(w)]
    south = [kind[h - 1][x] for x in range(w)]
    west = [kind[z][0] for z in range(h)]
    east = [kind[z][w - 1] for z in range(h)]
    return {
        "N": {"tiles": encode_rle_line([kind_to_id(v) for v in north]),
              "pass": encode_rle_line([kind_to_pass(v) for v in north])},
        "S": {"tiles": encode_rle_line([kind_to_id(v) for v in south]),
              "pass": encode_rle_line([kind_to_pass(v) for v in south])},
        "W": {"tiles": encode_rle_line([kind_to_id(v) for v in west]),
              "pass": encode_rle_line([kind_to_pass(v) for v in west])},
        "E": {"tiles": encode_rle_line([kind_to_id(v) for v in east]),
              "pass": encode_rle_line([kind_to_pass(v) for v in east])},
    }


# --- Новый, улучшенный код для hint/halo ---

def _sample_terrain_kind(
        wx: int, wz: int,
        stage_seeds: Dict[str, int],
        obs_params: Tuple[float, float, int],
        wat_params: Tuple[float, float, int]
) -> int:
    """Определяет тип ландшафта в одной мировой координате (замена для sample_kind)."""
    od, ofreq, ooct = obs_params
    wd, wfreq, woct = wat_params

    n_obs = fbm2d(stage_seeds["obstacles"], float(wx), float(wz), ofreq, octaves=ooct)
    n_w = fbm2d(stage_seeds["water"], float(wx), float(wz), wfreq, octaves=woct)

    if n_w < wd: return 2  # water
    return 1 if n_obs < od else 0  # obstacle or ground


def _generate_for_side(
        side: str,
        sampler_fn: Any,  # Это наша _sample_terrain_kind
        cx: int, cz: int, size: int, halo_t: int
) -> Tuple[Dict, Dict]:
    """Универсальный генератор hint и halo для одной стороны."""
    hint_line: List[int] = []
    halo_rows: List[List[int]] = []

    if side == "N":
        wz = cz * size - 1
        hint_line = [sampler_fn(cx * size + x, wz) for x in range(size)]
        halo_rows = [[sampler_fn(cx * size + x, wz - r) for x in range(size)] for r in range(halo_t, 0, -1)]
        return encode_rle_rows([hint_line]), encode_rle_rows(halo_rows)

    elif side == "S":
        wz = cz * size + size
        hint_line = [sampler_fn(cx * size + x, wz) for x in range(size)]
        halo_rows = [[sampler_fn(cx * size + x, wz + r - 1) for x in range(size)] for r in range(1, halo_t + 1)]
        return encode_rle_rows([hint_line]), encode_rle_rows(halo_rows)

    elif side == "W":
        wx = cx * size - 1
        hint_line = [sampler_fn(wx, cz * size + z) for z in range(size)]
        # RLE для вертикальных линий немного отличается
        halo_rows = [[sampler_fn(wx - r, cz * size + z) for z in range(size)] for r in range(halo_t, 0, -1)]
        return encode_rle_rows([[v] for v in hint_line]), encode_rle_rows(halo_rows)

    elif side == "E":
        wx = cx * size + size
        hint_line = [sampler_fn(wx, cz * size + z) for z in range(size)]
        halo_rows = [[sampler_fn(wx + r - 1, cz * size + z) for z in range(size)] for r in range(1, halo_t + 1)]
        return encode_rle_rows([[v] for v in hint_line]), encode_rle_rows(halo_rows)

    return {}, {}


def compute_hint_and_halo(
        stage_seeds: Dict[str, int], cx: int, cz: int, size: int,
        obs_cfg: Dict[str, Any], wat_cfg: Dict[str, Any], halo_t: int
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    Рассчитывает hint и halo, вызывая универсальный генератор для каждой стороны.
    """
    # Заранее готовим параметры для сэмплера
    obs_params = (float(obs_cfg.get("density", 0.12)), float(obs_cfg.get("freq", 1.0 / 28.0)),
                  int(obs_cfg.get("octaves", 3)))
    wat_params = (float(wat_cfg.get("density", 0.05)), float(wat_cfg.get("freq", 1.0 / 20.0)),
                  int(wat_cfg.get("octaves", 3)))

    def sampler(wx: int, wz: int) -> int:
        return _sample_terrain_kind(wx, wz, stage_seeds, obs_params, wat_params)

    hint: Dict[str, Any] = {}
    halo: Dict[str, Any] = {}

    for side in ["N", "S", "W", "E"]:
        hint[side], halo[side] = _generate_for_side(side, sampler, cx, cz, size, halo_t)

    return hint, halo