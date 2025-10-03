# editor/ui/layouts/properties_panel.py
from __future__ import annotations
from typing import Dict, Optional

from PySide6 import QtWidgets, QtCore
from PySide6.QtCore import Qt

from editor.core.theme import PALETTE
from editor.graph.custom_graph import CustomNodeGraph
from editor.nodes.base_node import GeneratorNode
from editor.ui.widgets.custom_controls import CollapsibleBox, SliderSpinCombo, SeedWidget


def create_properties_widget(parent: QtWidgets.QWidget) -> "AccordionProperties":
    props = AccordionProperties(parent=parent)
    props.setObjectName("PropertiesAccordion")
    props.setMinimumWidth(360)
    props.setSizePolicy(QtWidgets.QSizePolicy.Policy.Preferred, QtWidgets.QSizePolicy.Policy.Expanding)
    return props


class AccordionProperties(QtWidgets.QScrollArea):
    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        self.setObjectName("AccordionProperties")
        self.setWidgetResizable(True)
        self._graph: Optional[CustomNodeGraph] = None
        self._node: Optional[GeneratorNode] = None
        self._main_window: Optional[QtWidgets.QMainWindow] = None
        self._root = QtWidgets.QWidget()
        self._root.setStyleSheet(f"background-color: {PALETTE['dock_bg']};")
        self._vl = QtWidgets.QVBoxLayout(self._root)
        self._vl.setContentsMargins(6, 6, 6, 6)
        self._vl.setSpacing(8)
        self.setWidget(self._root)
        self.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)

    def set_graph(self, graph: Optional[CustomNodeGraph], main_window: Optional[QtWidgets.QMainWindow] = None) -> None:
        self._main_window = main_window
        if self._graph is graph: return
        if self._graph:
            try:
                self._graph.selection_changed.disconnect(self._on_graph_selection)
            except (RuntimeError, TypeError):
                pass
        self._graph = graph
        if self._graph is None: return
        self._graph.selection_changed.connect(self._on_graph_selection)
        self._on_graph_selection(self._graph.selected_nodes())

    @QtCore.Slot(list)
    def _on_graph_selection(self, selected_nodes: list) -> None:
        node = None
        if selected_nodes and isinstance(selected_nodes[0], GeneratorNode):
            node = selected_nodes[0]
        self.set_node(node)

    def clear_layout(self):
        while self._vl.count():
            item = self._vl.takeAt(0)
            if item is None: continue
            w = item.widget()
            if w: w.deleteLater()
            layout = item.layout()
            if layout:
                while layout.count():
                    child = layout.takeAt(0)
                    if child.widget(): child.widget().deleteLater()

    @QtCore.Slot(object)
    def set_node(self, node: Optional[GeneratorNode]):
        if self._node is node: return
        self._node = node
        self._rebuild()

    def _rebuild(self):
        self.clear_layout()
        node = self._node
        if not node:
            self._vl.addStretch(1)
            return
        meta = node.properties_meta()
        if not meta:
            self._vl.addStretch(1)
            return
        groups: Dict[str, CollapsibleBox] = {}
        for name, prop_meta in meta.items():
            if name in ('name', 'color', 'text_color', 'disabled'): continue
            group_name = prop_meta.get('group') or 'Params'
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
        kind = meta.get('type')
        value = node.get_property(name)
        update_slot = getattr(self._main_window, '_trigger_preview_update', None)
        is_float = kind in ('float', 'double', 'f')
        if meta.get('widget') == 'slider' and is_float:
            w = SliderSpinCombo(slider_on_left=False)
            p_range = meta.get('range', (0.0, 1.0))
            w.setRange(p_range[0], p_range[1])
            w.setValue(value)
            w.spinbox.valueChanged.connect(lambda val, nn=name: node.set_property(nn, val))
            if update_slot:
                w.editingFinished.connect(update_slot)
            return w
        if kind == 'line':
            w = QtWidgets.QLineEdit()
            if name == 'name' and value is None: value = node.name()
            w.setText(str(value))
            w.editingFinished.connect(lambda nn=name, ww=w: node.set_property(nn, ww.text()))
            if update_slot:
                w.editingFinished.connect(update_slot)
            return w
        elif is_float or kind in ('int', 'i'):
            w = QtWidgets.QDoubleSpinBox()
            if is_float:
                w.setDecimals(meta.get('decimals', 3))
                w.setSingleStep(meta.get('step', 0.01))
                w.setRange(meta.get('range', (-1e12, 1e12))[0], meta.get('range', (-1e12, 1e12))[1])
            else:
                w.setDecimals(0)
                w.setSingleStep(meta.get('step', 1))
                w.setRange(meta.get('range', (-4294967295, 4294967295))[0],
                           meta.get('range', (-4294967295, 4294967295))[1])
            w.setButtonSymbols(QtWidgets.QAbstractSpinBox.ButtonSymbols.NoButtons)
            w.setAlignment(Qt.AlignmentFlag.AlignRight)
            w.setMaximumWidth(meta.get('width', 100))
            w.setValue(float(value or 0))
            w.valueChanged.connect(lambda val, nn=name: node.set_property(nn, val))
            if update_slot:
                w.editingFinished.connect(update_slot)
            return w
        elif kind == 'seed':
            w = SeedWidget()
            w.setValue(int(value or 0))
            history = node._seed_history.get(name, [])
            w.set_history(history)
            w.valueChanged.connect(lambda val, nn=name: node.set_property(nn, int(val)))

            def on_finish():
                new_val = w.value()
                node.add_to_seed_history(name, new_val)
                w.set_history(node._seed_history.get(name, []))
                if update_slot:
                    update_slot()

            w.editingFinished.connect(on_finish)
            return w
        elif kind == 'check':
            w = QtWidgets.QCheckBox()
            w.setChecked(bool(value))
            w.toggled.connect(lambda state, nn=name: node.set_property(nn, state))
            if update_slot:
                w.toggled.connect(update_slot)
            return w
        elif kind == 'combo':
            w = QtWidgets.QComboBox()
            items = [str(x) for x in meta.get('items', [])]
            w.addItems(items)
            if str(value) in items:
                w.setCurrentText(str(value))
            w.currentTextChanged.connect(lambda text, nn=name: node.set_property(nn, text))
            if update_slot:
                w.currentTextChanged.connect(update_slot)
            return w
        return None
