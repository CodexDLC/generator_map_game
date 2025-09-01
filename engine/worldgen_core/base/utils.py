# engine/worldgen_core/base/utils.py
from __future__ import annotations
from typing import Any, Dict

from .constants import KIND_GROUND
from .rng import split_chunk_seed


def init_rng(seed: int, cx: int, cz: int) -> Dict[str, int]:
    """
    Сиды стадий генерации.
    - elevation: глобальный сид мира (гладкая непрерывность по всем чанкам)
    - temperature / humidity: детерминированы от мирового сида
    - obstacles / water: производные от chunk-seed (локальная вариативность)
    """
    base = split_chunk_seed(seed, cx, cz)
    return {
        "elevation":   seed,
        "temperature": seed ^ 0xA5A5A5A5,
        "humidity":    seed ^ 0x5A5A5A5A,
        "obstacles":   base ^ 0x55AA55AA,
        "water":       base ^ 0x33CC33CC,
    }


def make_empty_layers(size: int) -> Dict[str, Any]:
    """
    Пустой контейнер слоёв (без полей/fields; они заполняются отдельно).
    """
    return {
        "kind": [[KIND_GROUND for _ in range(size)] for _ in range(size)],
        "height_q": {"grid": [[0.0 for _ in range(size)] for _ in range(size)]},
    }
