# engine/worldgen_core/base/utils.py
from __future__ import annotations
from typing import Any, Dict

from .constants import KIND_GROUND
from .rng import split_chunk_seed


def init_rng(seed: int, cx: int, cz: int) -> Dict[str, int]:
    """Инициализирует сиды для разных стадий генерации чанка."""
    base = split_chunk_seed(seed, cx, cz)

    # <<< ГЛАВНОЕ ИЗМЕНЕНИЕ: Сид для высот теперь - это сам мировой сид! >>>
    # Это гарантирует, что OpenSimplex будет работать в едином пространстве.
    return {
        "elevation": seed,  # Используем ОРИГИНАЛЬНЫЙ сид мира
        "obstacles": base ^ 0x55AA,
        "water": base ^ 0x33CC,
    }


def make_empty_layers(size: int) -> Dict[str, Any]:
    """Создает пустую структуру для слоев карты."""
    return {
        "kind": [[KIND_GROUND for _ in range(size)] for _ in range(size)],
        # <<< ИЗМЕНЕНИЕ: Инициализируем grid для высот сразу >>>
        "height_q": {"grid": [[0.0 for _ in range(size)] for _ in range(size)]}
    }