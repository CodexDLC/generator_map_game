# ========================
# file: game_engine/core/preset/registry.py
# ========================
from __future__ import annotations
from typing import List
import os
from .errors import NotFoundError


# --- ИЗМЕНЕНИЕ: Указываем правильный путь к папке с пресетами ---
# Теперь движок будет искать пресеты в `game_engine_restructured/data/presets/`
_DEFAULT_PRESET_FOLDERS: List[str] = [
    os.path.join(
        # __file__ -> .../core/preset/registry.py
        # dirname(...) -> .../core/preset
        # dirname(...) -> .../core
        # dirname(...) -> .../game_engine_restructured
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        "data", "presets"
    ),
]


def resolve_preset_path(preset_id: str) -> str:
    """Map an id like 'world/base_default' to a JSON file path in presets/ tree."""
    rel = preset_id.replace("\\", "/").strip("/") + ".json"
    for root in _DEFAULT_PRESET_FOLDERS:
        candidate = os.path.join(root, rel)
        if os.path.isfile(candidate):
            return candidate
    # Добавил более детальный вывод ошибки
    raise NotFoundError(f"Preset id '{preset_id}' not found in presets/ folders: {', '.join(_DEFAULT_PRESET_FOLDERS)}")


def add_search_folder(path: str) -> None:
    path = os.path.abspath(path)
    if path not in _DEFAULT_PRESET_FOLDERS:
        _DEFAULT_PRESET_FOLDERS.append(path)