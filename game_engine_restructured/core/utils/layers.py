# game_engine/core/utils/layers.py
from __future__ import annotations
from typing import Any, Dict

# --- ИЗМЕНЕНИЕ: Импортируем весь модуль как const ---
from .. import constants as const


def make_empty_layers(size: int) -> Dict[str, Any]:
    """
    Создает пустой контейнер слоёв, теперь с 'overlay' слоем.
    """
    return {
        # --- ИЗМЕНЕНИЕ: Используем новые константы ---
        "surface": [[const.KIND_BASE_DIRT for _ in range(size)] for _ in range(size)],
        "navigation": [[const.NAV_PASSABLE for _ in range(size)] for _ in range(size)],
        "overlay": [[0 for _ in range(size)] for _ in range(size)],
        "height_q": {"grid": [[0.0 for _ in range(size)] for _ in range(size)]},
    }
