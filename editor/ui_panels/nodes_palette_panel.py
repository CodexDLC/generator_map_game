# ==============================================================================
# Файл: editor/ui_panels/nodes_palette_panel.py
# Назначение: Модуль для создания панели "Палитра Нодов".
# ВЕРСИЯ 1.1: Исправлен импорт QtCore.
# ==============================================================================
from PySide6 import QtWidgets, QtCore  # <-- ДОБАВЛЕН ИМПОРТ QtCore
from NodeGraphQt import NodesTreeWidget
from typing import cast


def create_nodes_palette_dock(main_window) -> None:
    """
    Создает и настраивает док-виджет с деревом доступных нодов.
    """
    # --- ИЗМЕНЕНИЕ: Используем get_active_graph() для инициализации ---
    nodes_tree = NodesTreeWidget(node_graph=main_window.get_active_graph())

    dock = QtWidgets.QDockWidget("Палитра Нодов", main_window)
    dock.setWidget(cast(QtWidgets.QWidget, nodes_tree))

    main_window.addDockWidget(QtCore.Qt.DockWidgetArea.LeftDockWidgetArea, dock)

    # Сохраняем ссылку на док-виджет, а не на его содержимое, для будущих манипуляций
    main_window.dock_nodes = dock