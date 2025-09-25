# ==============================================================================
# Файл: editor/ui_panels/properties_panel.py
# Назначение: Модуль для создания панели "Свойства Нода".
# ВЕРСИЯ 1.2: Добавлен objectName.
# ==============================================================================
from PySide6 import QtWidgets, QtCore
from NodeGraphQt import PropertiesBinWidget
from typing import cast


def create_properties_dock(main_window) -> None:
    """
    Создает и настраивает док-виджет для отображения свойств выбранной ноды.
    """
    props_bin = PropertiesBinWidget(node_graph=main_window.get_active_graph())
    props_bin.setObjectName("Виджет 'Свойства'") # Имя для внутреннего виджета

    dock = QtWidgets.QDockWidget("Свойства Нода", main_window)
    dock.setObjectName("Панель 'Свойства Нода'")
    dock.setWidget(cast(QtWidgets.QWidget, props_bin))

    main_window.addDockWidget(QtCore.Qt.DockWidgetArea.RightDockWidgetArea, dock)

    main_window.dock_props = dock
