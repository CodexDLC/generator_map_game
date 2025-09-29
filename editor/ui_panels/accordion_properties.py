# ==============================================================================
# editor/ui_panels/accordion_properties.py
# ВЕРСИЯ 2.1 (РЕФАКТОРИНГ): Использует чистое API графа.
# - Подключается к единому, чистому сигналу `selection_changed`.
# ==============================================================================

from __future__ import annotations
from typing import Dict, Optional, Any

from PySide6 import QtWidgets, QtCore
from PySide6.QtCore import Qt

from editor.theme import PALETTE
from editor.custom_graph import CustomNodeGraph # Используем для аннотации типов
from editor.nodes.base_node import GeneratorNode


class CollapsibleBox(QtWidgets.QGroupBox):
    def __init__(self, title: str, parent=None):
        super().__init__(title, parent)
        self.setObjectName("CollapsibleBox")
        self.setCheckable(True)
        self.setChecked(True)

        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(8, 6, 8, 8)
        lay.setSpacing(6)

        self._content = QtWidgets.QWidget(self)
        lay.addWidget(self._content)

        self.body = QtWidgets.QFormLayout(self._content)
        self.body.setContentsMargins(4, 4, 4, 4)
        self.body.setSpacing(6)

        self.toggled.connect(self._content.setVisible)


class AccordionProperties(QtWidgets.QScrollArea):
    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        self.setObjectName("AccordionProperties")
        self.setWidgetResizable(True)

        self._graph: Optional[CustomNodeGraph] = None
        self._node: Optional[GeneratorNode] = None

        self._root = QtWidgets.QWidget()
        self._root.setStyleSheet(f"background-color: {PALETTE['dock_bg']};")
        self._vl = QtWidgets.QVBoxLayout(self._root)
        self._vl.setContentsMargins(6, 6, 6, 6)
        self._vl.setSpacing(8)
        self._vl.addStretch(1)
        self.setWidget(self._root)
        self.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)

    def set_graph(self, graph: Optional[CustomNodeGraph]) -> None:
        if self._graph is graph:
            return

        # Отписываемся от старого графа, если он был
        if self._graph:
            try:
                self._graph.selection_changed.disconnect(self._on_graph_selection)
            except (RuntimeError, TypeError):
                pass # Сигнал мог быть уже отсоединен

        self._graph = graph
        if self._graph is None:
            return

        # РЕФАКТОРИНГ: Подключаемся к нашему новому, чистому сигналу
        self._graph.selection_changed.connect(self._on_graph_selection)

        # Сразу обновляем состояние на основе текущего выделения
        self._on_graph_selection(self._graph.selected_nodes())

    @QtCore.Slot(list)
    def _on_graph_selection(self, selected_nodes: list) -> None:
        """Слот для чистого сигнала `selection_changed`."""
        node = None
        if selected_nodes and isinstance(selected_nodes[0], GeneratorNode):
            node = selected_nodes[0]
        
        self.set_node(node)

    def clear_layout(self):
        """Очищает все виджеты со свойств."""
        while self._vl.count():
            item = self._vl.takeAt(0)
            if item is None: continue
            w = item.widget()
            if w:
                w.deleteLater()
            layout = item.layout()
            if layout:
                while layout.count():
                    child = layout.takeAt(0)
                    if child.widget():
                        child.widget().deleteLater()

    @QtCore.Slot(object)
    def set_node(self, node: Optional[GeneratorNode]):
        if self._node is node:
            return

        self._node = node
        self._rebuild()

    def _rebuild(self):
        """Перестраивает панель свойств для текущей выбранной ноды (_node)."""
        self.clear_layout()
        self._vl.addStretch(1)

        node = self._node
        if not node:
            return

        meta = node.properties_meta()
        if not meta:
            return

        groups: Dict[str, CollapsibleBox] = {}
        self._vl.takeAt(self._vl.count() - 1)

        for name, prop_meta in meta.items():
            group_name = prop_meta.get('group') or prop_meta.get('tab') or 'Params'

            if group_name not in groups:
                box = CollapsibleBox(group_name, self._root)
                groups[group_name] = box
                self._vl.addWidget(box)

            box = groups[group_name]

            widget = self._create_widget_for_property(node, name, prop_meta)
            if widget:
                label = prop_meta.get('label', name)
                box.body.addRow(label, widget)

        self._vl.addStretch(1)

    def _create_widget_for_property(self, node: GeneratorNode, name: str, meta: dict) -> Optional[QtWidgets.QWidget]:
        """Фабрика для создания виджета редактирования свойства."""
        kind = meta.get('type')
        value = node.get_property(name)

        if kind == 'line':
            w = QtWidgets.QLineEdit()
            w.setText(str(value))
            w.editingFinished.connect(lambda nn=name, ww=w: node.set_property(nn, ww.text()))
            return w

        elif kind in ('int', 'i', 'float', 'double', 'f'):
            is_float = kind in ('float', 'double', 'f')
            w = QtWidgets.QDoubleSpinBox() if is_float else QtWidgets.QSpinBox()

            if is_float:
                w.setDecimals(meta.get('decimals', 2))
                w.setSingleStep(meta.get('step', 0.1))
                w.setRange(meta.get('range', (-1e12, 1e12))[0], meta.get('range', (-1e12, 1e12))[1])
            else: # int
                w.setSingleStep(meta.get('step', 1))
                w.setRange(meta.get('range', (-(10**9), 10**9))[0], meta.get('range', (-(10**9), 10**9))[1])

            w.setButtonSymbols(QtWidgets.QAbstractSpinBox.ButtonSymbols.NoButtons)
            w.setAlignment(Qt.AlignRight)
            w.setMaximumWidth(meta.get('width', 100))
            w.setValue(value)
            w.valueChanged.connect(lambda val, nn=name: node.set_property(nn, val))
            return w

        elif kind == 'check':
            w = QtWidgets.QCheckBox()
            w.setChecked(bool(value))
            w.toggled.connect(lambda state, nn=name: node.set_property(nn, state))
            return w

        elif kind == 'combo':
            w = QtWidgets.QComboBox()
            items = [str(x) for x in meta.get('items', [])]
            w.addItems(items)
            if str(value) in items:
                w.setCurrentText(str(value))
            w.currentTextChanged.connect(lambda text, nn=name: node.set_property(nn, text))
            return w

        return None
