# ==============================================================================
# Файл: editor/ui_panels/nodes_palette_panel.py
# Назначение: Модуль для создания панели "Палитра Нодов".
# ВЕРСИЯ 1.2: Добавлен objectName.
# ==============================================================================
from PySide6 import QtWidgets, QtCore
from NodeGraphQt import NodesTreeWidget
from typing import cast


def create_nodes_palette_dock(main_window) -> None:
    """
    Создает и настраивает док-виджет с деревом доступных нодов.
    """
    nodes_tree = NodesTreeWidget(node_graph=main_window.get_active_graph())
    nodes_tree.setObjectName("Виджет 'Дерево Нодов'") # Имя для внутреннего виджета

    dock = QtWidgets.QDockWidget("Палитра Нодов", main_window)
    dock.setObjectName("Панель 'Палитра Нодов'")
    dock.setWidget(cast(QtWidgets.QWidget, nodes_tree))

    main_window.addDockWidget(QtCore.Qt.DockWidgetArea.LeftDockWidgetArea, dock)

    main_window.dock_nodes = dock
