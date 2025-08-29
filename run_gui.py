
"""
Запуск простого UI для просмотра чанков (Stage C минималка).
Запуск: python run_gui.py
"""
from __future__ import annotations
import sys, pathlib

# Убедимся, что корень проекта в sys.path (для импорта engine/*)
ROOT = pathlib.Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from worldgen_ui.app.main import main

if __name__ == "__main__":
    main()
