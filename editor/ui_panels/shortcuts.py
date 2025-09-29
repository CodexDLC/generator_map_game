# ==============================================================================
# Файл: editor/ui_panels/shortcuts.py
# Назначение: Глобальные хоткеи для компоновки V2.
# Особенности:
#   - В PySide6 класс QShortcut находится в QtGui.
#   - Ставим F1/F2 (показ/скрытие палитры и аутлайнера) и Ctrl+Enter (APPLY).
#   - Не создаём дубликаты хоткеев при повторном вызове.
# ==============================================================================

from __future__ import annotations
from typing import List, Optional, Callable

from PySide6 import QtWidgets, QtCore, QtGui


def _safe_call(obj, name):
    fn = getattr(obj, name, None)
    return fn if callable(fn) else (lambda: None)


def install_shortcuts(main_window: QtWidgets.QMainWindow) -> None:
    """
    Подвешивает глобальные хоткеи для V2. Вызывать один раз после сборки UI.
    """
    if getattr(main_window, "_shortcuts_v2_installed", False):
        return

    shortcuts: List[QtGui.QShortcut] = []

    def add(seq: str,
            slot: Callable[[], None],
            parent: Optional[QtWidgets.QWidget] = None,
            context: QtCore.Qt.ShortcutContext = QtCore.Qt.ApplicationShortcut) -> None:
        w = parent or main_window
        sc = QtGui.QShortcut(QtGui.QKeySequence(seq), w)  # ВАЖНО: QtGui.QShortcut
        sc.setContext(context)
        sc.activated.connect(slot)
        shortcuts.append(sc)

    # F1: скрыть/показать левую палитру
    add("Ctrl+F1", _safe_call(main_window, "toggle_left_palette"))

    # F2: скрыть/показать правый outliner
    add("Ctrl+F2", _safe_call(main_window, "toggle_right_outliner"))

    # Ctrl+Enter: APPLY (если есть _trigger_apply — используем его)
    trig = getattr(main_window, "_trigger_apply", None)
    if callable(trig):
        add("Ctrl+Return", trig)
        add("Ctrl+Enter", trig)
    else:
        def _click_apply() -> None:
            btn = main_window.findChild(QtWidgets.QPushButton, "apply_button_right_outliner")
            if btn:
                btn.animateClick(10)
                return
            for b in main_window.findChildren(QtWidgets.QPushButton):
                try:
                    if b.text().strip().lower() == "apply":
                        b.animateClick(10)
                        return
                except Exception:
                    pass
        add("Ctrl+Return", _click_apply)
        add("Ctrl+Enter", _click_apply)



    # Маркеры, чтобы не устанавливать повторно и не дать GC съесть хоткеи
    main_window._shortcuts_v2_installed = True
    main_window._shortcuts_v2_ref = shortcuts

