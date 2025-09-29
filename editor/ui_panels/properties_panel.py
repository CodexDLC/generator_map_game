# ==============================================================================
# Файл: editor/ui_panels/properties_panel.py
# Назначение: Панель «Свойства» нод
#
# ВЕРСИЯ 2.0:
#   - NEW: make_properties_widget(main_window) — возвращает встраиваемый виджет (AccordionProperties).
#   - LEGACY: create_properties_dock(main_window) — док-обёртка (для V1/restoreState).
#   - Совместимость: кладёт ссылку на бин в main_window.props_bin и, если есть граф,
#     сразу делает props_bin.set_graph(main_window.graph).
# ==============================================================================

from __future__ import annotations
from PySide6 import QtWidgets, QtCore

# твой виджет свойств
from editor.ui_panels.accordion_properties import AccordionProperties


def make_properties_widget(main_window) -> QtWidgets.QWidget:
    props = AccordionProperties(parent=main_window)            # ← без графа
    props.setObjectName("PropertiesAccordion")
    main_window.props_bin = props                              # ссылка наружу
    if getattr(main_window, "graph", None):                    # если граф уже есть — биндим
        props.set_graph(main_window.graph)
    props.setMinimumWidth(360)
    props.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Expanding)
    return props



def create_properties_dock(main_window) -> QtWidgets.QDockWidget:
    """
    (V1 совместимость) Создаёт док-обёртку для панели «Свойства».
    Использует тот же контент, что и фабрика V2.
    """
    content = make_properties_widget(main_window)

    dock = QtWidgets.QDockWidget("Свойства", main_window)
    dock.setObjectName("Dock_Properties")
    dock.setFeatures(QtWidgets.QDockWidget.DockWidgetMovable |
                     QtWidgets.QDockWidget.DockWidgetFloatable)
    dock.setWidget(content)
    dock.setMinimumWidth(380)

    # добавить в правую зону по умолчанию
    try:
        main_window.addDockWidget(QtCore.Qt.DockWidgetArea.RightDockWidgetArea, dock)
    except Exception:
        pass

    # для старого кода, который ожидал атрибут
    try:
        main_window.dock_props = dock
    except Exception:
        pass

    return dock
