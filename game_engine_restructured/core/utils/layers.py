# game_engine/core/utils/layers.py
from __future__ import annotations
from typing import Any, Dict

# Импортируем наши новые константы
from ..constants import KIND_GROUND, NAV_PASSABLE


def make_empty_layers(size: int) -> Dict[str, Any]:
    """
    Создает пустой контейнер слоёв, теперь с 'overlay' слоем для дорог.
    """
    return {
        "surface": [[KIND_GROUND for _ in range(size)] for _ in range(size)],
        "navigation": [[NAV_PASSABLE for _ in range(size)] for _ in range(size)],
        # --- НОВЫЙ СЛОЙ: 0 означает "нет оверлея" ---
        "overlay": [[0 for _ in range(size)] for _ in range(size)],
        "height_q": {"grid": [[0.0 for _ in range(size)] for _ in range(size)]},
    }
