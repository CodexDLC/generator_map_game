# game_engine/core/utils/layers.py
from __future__ import annotations
from typing import Any, Dict

from ..constants import KIND_GROUND

def make_empty_layers(size: int) -> Dict[str, Any]:
    """
    Создает пустой контейнер слоёв.
    """
    return {
        "kind": [[KIND_GROUND for _ in range(size)] for _ in range(size)],
        "height_q": {"grid": [[0.0 for _ in range(size)] for _ in range(size)]},
    }

