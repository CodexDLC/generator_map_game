# game_engine/story_features/features/base_feature.py
from __future__ import annotations
from typing import Any

from ...core.types import GenResult


# Базовый класс или протокол для всех наших "кисточек"
class FeatureBrush:
    def __init__(self, result: GenResult, preset: Any):
        self.result = result
        self.preset = preset
        # --- ИЗМЕНЕНИЕ: Получаем доступ к обоим слоям ---
        self.surface_grid = result.layers["surface"]
        self.nav_grid = result.layers["navigation"]
        self.size = len(self.surface_grid)

    def apply(self, **kwargs):
        raise NotImplementedError
