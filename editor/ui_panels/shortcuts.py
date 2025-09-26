# ==============================================================================
# Файл: editor/ui/shortcuts.py
# Назначение: Глобальные шорткаты.
# ВЕРСИЯ 2.0: Убран Shift+F5 (тайловый запуск). Оставляем только F5 -> _on_apply_clicked.
# ==============================================================================
from PySide6 import QtGui, QtCore


def install_global_shortcuts(mw):
    def add(seq, cb):
        sc = QtGui.QShortcut(QtGui.QKeySequence(seq), mw)
        sc.setContext(QtCore.Qt.ShortcutContext.ApplicationShortcut)
        sc.activated.connect(cb)

    # Сохранить проект
    add("Ctrl+S", mw.on_save_project)

    # Единый запуск генерации (цельный расчёт)
    # Делаем безопасно: если метода нет, шорткат не добавляем.
    if hasattr(mw, "_on_apply_clicked"):
        add("F5", mw._on_apply_clicked)
