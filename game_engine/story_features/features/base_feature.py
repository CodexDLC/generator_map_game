# game_engine/story_features/features/base_feature.py
from __future__ import annotations
from typing import Dict, Any

from ...core.types import GenResult

# Базовый класс или протокол для всех наших "кисточек"
class FeatureBrush:
    def __init__(self, result: GenResult, preset: Any):
        self.result = result
        self.preset = preset
        self.kind_grid = result.layers["kind"]
        self.size = len(self.kind_grid)

    def apply(self, **kwargs):
        raise NotImplementedError