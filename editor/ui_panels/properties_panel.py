# ==============================================================================
# Файл: editor/ui_panels/properties_panel.py
# Назначение: Модуль для создания панели "Свойства Нода".
# ВЕРСИЯ 1.1: Исправлен импорт QtCore.
# ==============================================================================
from PySide6 import QtWidgets, QtCore  # <-- ДОБАВЛЕН ИМПОРТ QtCore
from NodeGraphQt import PropertiesBinWidget
from typing import cast

def create_properties_dock(main_window) -> None:
    """
    Создает и настраивает док-виджет для отображения свойств выбранной ноды.
    """
    props_bin = PropertiesBinWidget(node_graph=main_window.graph)

    dock = QtWidgets.QDockWidget("Свойства Нода", main_window)
    dock.setWidget(cast(QtWidgets.QWidget, props_bin))

    # --- ИСПРАВЛЕНИЕ: Используем QtCore.Qt вместо QtWidgets.Qt ---
    main_window.addDockWidget(QtCore.Qt.DockWidgetArea.RightDockWidgetArea, dock)

    main_window.dock_props = dock