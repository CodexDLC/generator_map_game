# game_engine/core/utils/layers.py
from __future__ import annotations
from typing import Any, Dict

# Импортируем наши новые константы
from ..constants import KIND_GROUND, NAV_PASSABLE

def make_empty_layers(size: int) -> Dict[str, Any]:
    """
    Создает пустой контейнер слоёв с разделением на 'surface' и 'navigation'.
    """
    return {
        # Слой для визуализации (текстуры Terrain3D)
        "surface": [[KIND_GROUND for _ in range(size)] for _ in range(size)],
        # Слой для проходимости (Pathfinder и сервер)
        "navigation": [[NAV_PASSABLE for _ in range(size)] for _ in range(size)],
        # Слой высот остается как есть
        "height_q": {"grid": [[0.0 for _ in range(size)] for _ in range(size)]},
    }