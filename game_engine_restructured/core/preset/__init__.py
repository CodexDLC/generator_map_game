# ========================
# file: game_engine/core/preset/__init__.py
# ========================
from .version import CURRENT_PRESET_VERSION
from .model import Preset
from .loader import load_preset, deep_merge
from .defaults import DEFAULT_BASE_PRESET_V2

__all__ = [
    "CURRENT_PRESET_VERSION",
    "Preset",
    "load_preset",
    "deep_merge",
    "DEFAULT_BASE_PRESET_V2",
]

