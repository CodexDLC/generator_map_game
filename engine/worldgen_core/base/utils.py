# engine/worldgen_core/base/utils.py
from __future__ import annotations
from typing import Any, Dict

from .constants import KIND_GROUND
from .rng import split_chunk_seed

def init_rng(seed: int, cx: int, cz: int) -> Dict[str, int]:
    """Инициализирует сиды для разных стадий генерации чанка."""
    base = split_chunk_seed(seed, cx, cz)
    # Теперь мы создаем отдельные, уникальные сиды для каждой стадии,
    # используя побитовую операцию XOR с разными константами.
    return {
        "elevation": base ^ 0x01,
        "obstacles": base ^ 0x55AA, # Добавленный сид
        "water":     base ^ 0x33CC, # Добавленный сид
    }

def make_empty_layers(size: int) -> Dict[str, Any]:
    """Создает пустую структуру для слоев карты."""
    return {
        "kind": [[KIND_GROUND for _ in range(size)] for _ in range(size)],
        "height_q": {"grid": []}
    }