# editor/ui/shortcuts.py
from PySide6 import QtGui, QtCore

def install_global_shortcuts(mw):
    def add(seq, cb):
        sc = QtGui.QShortcut(QtGui.QKeySequence(seq), mw)
        sc.setContext(QtCore.Qt.ShortcutContext.ApplicationShortcut)
        sc.activated.connect(cb)

    # Сохранить проект
    add("Ctrl+S", mw.on_save_project)
    # Запуск генерации
    add("F5", mw._on_apply_clicked)
    add("Shift+F5", mw._on_apply_tiled_clicked)
