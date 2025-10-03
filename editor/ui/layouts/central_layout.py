# ==============================================================================
# Файл: editor/ui/central_layout.py
# ВЕРСИЯ 3.1 (HOTFIX): Исправлено создание NodesPaletteWidget.
# - В конструктор виджета теперь передается корректный родитель (main_window).
# ==============================================================================

from __future__ import annotations
from typing import cast

from PySide6 import QtWidgets, QtCore

from editor.graph.custom_graph import CustomNodeGraph
from editor.nodes.node_registry import register_all_nodes
from editor.ui.layouts.nodes_palette_panel import NodesPaletteWidget
from editor.ui.layouts.right_outliner_panel import RightOutlinerWidget


def create_bottom_work_area_v2(main_window) -> tuple[QtWidgets.QWidget, CustomNodeGraph, NodesPaletteWidget, RightOutlinerWidget]:
    """
    Создает и компонует нижнюю рабочую область: [Палитра] | [Граф] | [Outliner].

    Возвращает кортеж: (контейнер, объект_графа, палитра, аутлайнер),
    чтобы MainWindow мог сам ими управлять и связывать сигналы.
    """
    # 1. Создаем компоненты
    graph = CustomNodeGraph()
    register_all_nodes(graph)
    graph_widget = graph.widget
    graph_widget.setObjectName("GraphWidgetMain")
    graph_widget.setFocusPolicy(QtCore.Qt.StrongFocus)

    # РЕФАКТОРИНГ: Передаем корректный родительский виджет в конструктор
    left_palette = NodesPaletteWidget(parent=main_window)
    right_outliner = RightOutlinerWidget(main_window)

    # 2. Компонуем их в сплиттере
    split_h = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
    split_h.setObjectName("BottomWorkSplitH")
    split_h.setChildrenCollapsible(False)
    split_h.addWidget(left_palette)
    split_h.addWidget(cast(QtWidgets.QWidget, graph_widget))
    split_h.addWidget(right_outliner)
    split_h.setSizes([260, 1000, 320])

    # 3. Возвращаем все созданные объекты, чтобы вызывающий код мог ими управлять
    return split_h, graph, left_palette, right_outliner
