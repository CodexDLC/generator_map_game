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
    # --- ИЗМЕНЕНИЕ: Используем get_active_graph() для инициализации ---
    props_bin = PropertiesBinWidget(node_graph=main_window.get_active_graph())

    dock = QtWidgets.QDockWidget("Свойства Нода", main_window)
    dock.setWidget(cast(QtWidgets.QWidget, props_bin))

    main_window.addDockWidget(QtCore.Qt.DockWidgetArea.RightDockWidgetArea, dock)

    # Сохраняем ссылку на док-виджет
    main_window.dock_props = dock
