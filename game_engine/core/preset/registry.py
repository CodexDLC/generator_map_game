# ========================
# file: game_engine/core/preset/registry.py
# ========================
from __future__ import annotations
from typing import List
import os
from .errors import NotFoundError


# Default search roots (can be extended by the app)
_DEFAULT_PRESET_FOLDERS: List[str] = [
    os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "presets"
    ),
]


def resolve_preset_path(preset_id: str) -> str:
    """Map an id like 'world/base_default' to a JSON file path in presets/ tree."""
    rel = preset_id.replace("\\", "/").strip("/") + ".json"
    for root in _DEFAULT_PRESET_FOLDERS:
        candidate = os.path.join(root, rel)
        if os.path.isfile(candidate):
            return candidate
    raise NotFoundError(f"Preset id '{preset_id}' not found in presets/ folders")


def add_search_folder(path: str) -> None:
    path = os.path.abspath(path)
    if path not in _DEFAULT_PRESET_FOLDERS:
        _DEFAULT_PRESET_FOLDERS.append(path)
