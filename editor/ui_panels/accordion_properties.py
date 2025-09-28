from __future__ import annotations
from typing import Dict, Optional

from NodeGraphQt import NodeGraph, BaseNode
from PySide6 import QtWidgets, QtCore
from PySide6.QtCore import Qt

from editor.theme import PALETTE


class CollapsibleBox(QtWidgets.QGroupBox):
    def __init__(self, title: str, parent=None):
        super().__init__(title, parent)
        self.setObjectName("CollapsibleBox")
        self.setCheckable(True)
        self.setChecked(True)

        # Лэйаут: оставим небольшие внутренние поля,
        # контент пойдёт под заголовком, не заезжая на него
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(8, 6, 8, 8)
        lay.setSpacing(6)

        self._content = QtWidgets.QWidget(self)
        lay.addWidget(self._content)

        self.body = QtWidgets.QFormLayout(self._content)
        self.body.setContentsMargins(4, 4, 4, 4)
        self.body.setSpacing(6)

        # Раскрытие/скрытие — ок
        self.toggled.connect(self._content.setVisible)

    def set_content_enabled(self, enabled: bool):
        self._content.setEnabled(bool(enabled))

class AccordionProperties(QtWidgets.QScrollArea):
    def __init__(self, graph: NodeGraph, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        self.setObjectName("AccordionProperties")
        self.setWidgetResizable(True)
        self._graph = graph
        self._node: Optional[BaseNode] = None
        self._root = QtWidgets.QWidget()
        self._root.setStyleSheet(f"background-color: {PALETTE['dock_bg']};")
        self._vl = QtWidgets.QVBoxLayout(self._root)
        self._vl.setContentsMargins(6, 6, 6, 6)
        self._vl.setSpacing(8)
        self._vl.addStretch(1)
        self.setWidget(self._root)
        self.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        # В твоем коде используется node_selection_changed, но в NodeGraphQt
        # более распространен сигнал node_selected. Проверяем оба.
        if hasattr(self._graph, 'node_selection_changed'):
            self._graph.node_selection_changed.connect(self.set_node)
        elif hasattr(self._graph, 'node_selected'):
            self._graph.node_selected.connect(self.set_node)

    def clear(self):
        while self._vl.count():
            item = self._vl.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

    @QtCore.Slot(object)
    def set_node(self, node):
        # граф иногда шлёт список; берём первый
        if isinstance(node, (list, tuple)):
            node = node[0] if node else None

        # если пришло пусто — не очищаем, оставляем предыдущую ноду
        if node is None:
            return

        # если это та же нода — не перестраиваем
        if self._node is node:
            return

        self._node = node
        self._rebuild()

    def _rebuild(self):
        self.clear()
        n = self._node
        if not n:
            self._vl.addStretch(1)
            return

        groups: Dict[str, CollapsibleBox] = {}
        meta = getattr(n, "_prop_meta", {}) or {}
        ui_state = getattr(n, "_ui_state", {}) if hasattr(n, "_ui_state") else {}

        def group(key: str) -> CollapsibleBox:
            if key not in groups:
                box = CollapsibleBox(key, self._root)
                groups[key] = box
                self._vl.addWidget(box)

                prop_enable = f"grp_{key}__enabled"

                # гарантируем, что свойство есть в модели (но не видно в стандартной панели)
                try:
                    n.get_property(prop_enable)
                except Exception:
                    try:
                        n.model.add_property(prop_enable, True, tab='__ui__')
                    except Exception:
                        pass

                try:
                    enabled_val = bool(n.get_property(prop_enable))
                except Exception:
                    enabled_val = True

                box.setChecked(enabled_val)
                box.set_content_enabled(enabled_val)

                def _on_toggled(state, prop=prop_enable, b=box, node=n):
                    try:
                        node.set_property(prop, bool(state))
                    except Exception:
                        try:
                            node.model.add_property(prop, bool(state), tab='__ui__')
                            node.set_property(prop, bool(state))
                        except Exception:
                            pass
                    b.set_content_enabled(bool(state))

                box.toggled.connect(_on_toggled)

                # восстановим «раскрытость» секции (опционально)
                expanded = ui_state.get(key, {}).get("expanded", True)
                box._content.setVisible(bool(expanded))
                box.toggled.connect(lambda st, k=key: ui_state.setdefault(k, {}).update(expanded=bool(st)))

            return groups[key]

        for name, m in meta.items():
            grp = m.get('group') or m.get('tab') or 'Params'
            box = group(str(grp))
            label = m.get('label', name)
            kind = m.get('type', 'line')
            items = m.get('items', [])

            if kind == 'line':
                w = QtWidgets.QLineEdit()
                v = n.get_property(name)
                w.setText("" if v is None else str(v))
                w.setAlignment(Qt.AlignLeft)
                w.editingFinished.connect(lambda nn=name, ww=w: n.set_property(nn, ww.text()))
                box.body.addRow(label, w)

            elif kind in ('int', 'i'):
                w = QtWidgets.QSpinBox()
                # метаданные для диапазона/шага/ширины
                lo, hi = m.get('range', (-(10 ** 9), 10 ** 9))
                step = m.get('step', 1)
                width = m.get('width', 96)
                w.setRange(int(lo), int(hi))
                w.setSingleStep(int(step))
                w.setButtonSymbols(QtWidgets.QAbstractSpinBox.ButtonSymbols.NoButtons)
                w.setAlignment(Qt.AlignRight)
                w.setMaximumWidth(int(width))
                try:
                    w.setValue(int(n.get_property(name)))
                except Exception:
                    pass
                w.valueChanged.connect(lambda val, nn=name: n.set_property(nn, int(val)))
                box.body.addRow(label, w)

            elif kind in ('float', 'double', 'f'):
                w = QtWidgets.QDoubleSpinBox()
                lo, hi = m.get('range', (-1e12, 1e12))
                step = m.get('step', 0.1)
                decimals = m.get('decimals', 2)
                width = m.get('width', 100)
                w.setDecimals(int(decimals))
                w.setRange(float(lo), float(hi))
                w.setSingleStep(float(step))
                w.setButtonSymbols(QtWidgets.QAbstractSpinBox.ButtonSymbols.NoButtons)
                w.setAlignment(Qt.AlignRight)
                w.setMaximumWidth(int(width))
                try:
                    w.setValue(float(n.get_property(name)))
                except Exception:
                    pass
                w.valueChanged.connect(lambda val, nn=name: n.set_property(nn, float(val)))
                box.body.addRow(label, w)

            elif kind == 'check':
                w = QtWidgets.QCheckBox()
                w.setChecked(bool(n.get_property(name)))
                w.toggled.connect(lambda state, nn=name: n.set_property(nn, bool(state)))
                box.body.addRow(label, w)

            elif kind == 'combo':
                w = QtWidgets.QComboBox()
                w.addItems([str(x) for x in items])
                cur = str(n.get_property(name))
                li = [str(x) for x in items]
                if cur in li:
                    w.setCurrentIndex(li.index(cur))
                w.currentTextChanged.connect(lambda text, nn=name: n.set_property(nn, text))
                box.body.addRow(label, w)

            else:
                box.body.addRow(label, QtWidgets.QLabel("(unsupported)"))

        self._vl.addStretch(1)