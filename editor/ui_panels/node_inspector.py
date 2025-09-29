# ==============================================================================
# Виджет-инспектор выбранной ноды
# Показывает: имя, класс/категорию/ID, кнопку цвета (если возможно), списки входов/выходов.
# Сам подхватывает выделение из графа.
# ==============================================================================

from __future__ import annotations
from typing import Optional, Any, List, Tuple

from PySide6 import QtWidgets, QtCore, QtGui


class NodeInspectorWidget(QtWidgets.QWidget):
    def __init__(self, main_window: QtWidgets.QMainWindow, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("NodeInspector")

        self._mw = main_window
        self._graph = getattr(main_window, "graph", None)
        self._node = None  # текущая выбранная нода

        # ---------- UI ----------
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(6)

        # Заголовок
        title = QtWidgets.QLabel("Инспектор ноды")
        title.setStyleSheet("font-weight: bold;")
        root.addWidget(title)

        # Имя
        form = QtWidgets.QFormLayout()
        form.setLabelAlignment(QtCore.Qt.AlignRight)
        root.addLayout(form)

        self._name_edit = QtWidgets.QLineEdit(self)
        self._name_edit.setPlaceholderText("Имя ноды…")
        self._name_edit.editingFinished.connect(self._apply_name)
        form.addRow("Name:", self._name_edit)

        # Метаданные (RO)
        self._class_lbl = QtWidgets.QLabel("")
        self._class_lbl.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
        form.addRow("Class:", self._class_lbl)

        self._category_lbl = QtWidgets.QLabel("")
        self._category_lbl.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
        form.addRow("Category:", self._category_lbl)

        self._id_lbl = QtWidgets.QLabel("")
        self._id_lbl.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
        form.addRow("ID:", self._id_lbl)

        # Цвет
        clr_row = QtWidgets.QHBoxLayout()
        self._color_btn = QtWidgets.QPushButton("Цвет…")
        self._color_btn.clicked.connect(self._pick_color)
        clr_row.addWidget(self._color_btn, 0)
        clr_row.addStretch(1)
        form.addRow("Color:", clr_row)

        # Порты
        ports_box = QtWidgets.QGroupBox("Порты")
        root.addWidget(ports_box, 1)
        ports_lay = QtWidgets.QHBoxLayout(ports_box)

        self._inputs = QtWidgets.QListWidget()
        self._inputs.setAlternatingRowColors(True)
        self._inputs.setSelectionMode(QtWidgets.QAbstractItemView.NoSelection)
        ports_lay.addWidget(self._inputs)

        self._outputs = QtWidgets.QListWidget()
        self._outputs.setAlternatingRowColors(True)
        self._outputs.setSelectionMode(QtWidgets.QAbstractItemView.NoSelection)
        ports_lay.addWidget(self._outputs)

        # Заглушка, когда ноды не выбрано
        self._empty_lbl = QtWidgets.QLabel("нет выбранной ноды")
        self._empty_lbl.setAlignment(QtCore.Qt.AlignCenter)
        self._empty_lbl.setStyleSheet("color:#aaaaaa;")
        root.addWidget(self._empty_lbl)

        self._update_enabled(False)

        # ---------- Подписки на граф ----------
        self._hook_graph_events()

        # Первичная синхронизация
        self.refresh_from_selection()

    # ------------------------------------------------------------------ public

    def bind_graph(self, graph) -> None:
        """Если граф поменялся — можно привязать новый."""
        self._graph = graph
        self._hook_graph_events()
        self.refresh_from_selection()

    # ----------------------------------------------------------------- internal

    def _hook_graph_events(self) -> None:
        g = self._graph
        if not g:
            return
        # Защита от двойной подписки
        if getattr(self, "_graph_hooks_installed", False):
            return

        try:
            if hasattr(g, "node_selection_changed"):
                g.node_selection_changed.connect(self.refresh_from_selection)
            elif hasattr(g, "node_selected"):
                g.node_selected.connect(self.refresh_from_selection)
            if hasattr(g, "node_deleted"):
                g.node_deleted.connect(self.refresh_from_selection)
            if hasattr(g, "node_created"):
                g.node_created.connect(self.refresh_from_selection)
        except Exception:
            pass

        self._graph_hooks_installed = True

    def _update_enabled(self, enabled: bool) -> None:
        for w in (self._name_edit, self._color_btn, self._inputs, self._outputs):
            w.setEnabled(enabled)
        self._empty_lbl.setVisible(not enabled)

    def refresh_from_selection(self) -> None:
        g = self._graph
        if not g:
            self._node = None
            self._update_enabled(False)
            return

        try:
            sel = g.selected_nodes()
        except Exception:
            sel = []

        if not sel:
            self._node = None
            self._name_edit.setText("")
            self._class_lbl.setText("")
            self._category_lbl.setText("")
            self._id_lbl.setText("")
            self._inputs.clear()
            self._outputs.clear()
            self._update_enabled(False)
            return

        n = sel[0]
        self._node = n

        # Имя
        try:
            nm = n.name()
        except Exception:
            nm = ""
        self._name_edit.setText(str(nm))

        # Метаданные
        cls = n.__class__
        cls_name = getattr(cls, "__name__", "Node")
        category = getattr(n, "NODE_CATEGORY", getattr(cls, "NODE_CATEGORY", ""))
        node_id = getattr(n, "id", "") or getattr(n, "NODE_ID", "")

        self._class_lbl.setText(str(cls_name))
        self._category_lbl.setText(str(category))
        self._id_lbl.setText(str(node_id))

        # Цвет — попытаемся вытащить из property/метода
        color_hex = None
        try:
            if hasattr(n, "get_property"):
                color_hex = n.get_property("bg_color", None)
        except Exception:
            pass
        if not color_hex:
            # иногда ноды хранят QColor напрямую
            qc = getattr(n, "color", None)
            if isinstance(qc, QtGui.QColor):
                color_hex = qc.name()
        self._apply_color_btn(color_hex or "#3c3c3c")

        # Порты
        self._fill_ports(n)

        self._update_enabled(True)

    def _apply_name(self) -> None:
        n = self._node
        if not n:
            return
        text = self._name_edit.text().strip()
        try:
            if hasattr(n, "set_name"):
                n.set_name(text)
            elif hasattr(n, "setTitle"):
                n.setTitle(text)
        except Exception:
            pass

    def _apply_color_btn(self, hex_color: str) -> None:
        # окрашиваем саму кнопку
        self._color_btn.setStyleSheet(f"background-color:{hex_color};")

    def _pick_color(self) -> None:
        n = self._node
        if not n:
            return
        # стартовый цвет
        start = "#3c3c3c"
        try:
            if hasattr(n, "get_property"):
                start = n.get_property("bg_color", start)
        except Exception:
            pass
        c = QtWidgets.QColorDialog.getColor(QtGui.QColor(start), self, "Цвет ноды")
        if not c.isValid():
            return
        hex_c = c.name()
        self._apply_color_btn(hex_c)

        # применяем к ноде — мягко, с проверками
        try:
            if hasattr(n, "set_bg_color"):
                n.set_bg_color(c)
            elif hasattr(n, "set_color"):
                n.set_color(c)
            elif hasattr(n, "setProperty"):
                n.setProperty("bg_color", hex_c)
            elif hasattr(n, "set_property"):
                n.set_property("bg_color", hex_c)
        except Exception:
            pass

    def _fill_ports(self, n):
        self._inputs.clear();
        self._outputs.clear()

        def _safe_list(v):
            try:
                return list(v())
            except Exception:
                try:
                    return list(v)
                except Exception:
                    return []

        def _label(p):
            name = ""
            try:
                name = p.name() if hasattr(p, "name") else getattr(p, "name", "")
            except Exception:
                pass
            if not name:
                name = getattr(p, "PORT_NAME", "") or str(p)
            return name

        def _connections(p):
            # NodeGraphQt обычно даёт p.connected_ports() / p.connections()
            for attr in ("connected_ports", "connections"):
                fn = getattr(p, attr, None)
                if callable(fn):
                    return _safe_list(fn)
            return []

        def _make_item(p):
            name = _label(p)
            conns = _connections(p)
            it = QtWidgets.QListWidgetItem(f"{name}  [{len(conns)}]")
            if conns:
                tips = []
                for other in conns:
                    try:
                        onode = getattr(other, "node", None)
                        oname = onode.name() if callable(getattr(onode, "name", None)) else getattr(onode, "name", "")
                        opname = other.name() if callable(getattr(other, "name", None)) else getattr(other, "name", "")
                        tips.append(f"{oname}:{opname}")
                    except Exception:
                        pass
                it.setToolTip("\n".join(tips))
            return it

        # собрать входы
        ins = []
        try:
            if hasattr(n, "inputs"): ins = list(n.inputs())
        except Exception:
            pass
        for p in ins:
            self._inputs.addItem(_make_item(p))

        # собрать выходы
        outs = []
        try:
            if hasattr(n, "outputs"): outs = list(n.outputs())
        except Exception:
            pass
        for p in outs:
            self._outputs.addItem(_make_item(p))


def make_node_inspector_widget(main_window: QtWidgets.QMainWindow) -> QtWidgets.QWidget:
    """
    Фабрика, как ты просил. Возвращает готовый инспектор.
    """
    w = NodeInspectorWidget(main_window)
    return w

