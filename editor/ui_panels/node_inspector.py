# ==============================================================================
# Файл: editor/ui_panels/node_inspector.py
# ВЕРСИЯ 2.1 (ИСПРАВЛЕНИЕ): Исправлена установка цвета.
# - Метод _pick_color теперь корректно преобразует объект QColor
#   в кортеж (r, g, b), который ожидает библиотека NodeGraphQt.
#   Это решает проблему с TypeError при перерисовке ноды.
# ==============================================================================

from __future__ import annotations
from typing import Optional

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

        title = QtWidgets.QLabel("Инспектор ноды")
        title.setStyleSheet("font-weight: bold;")
        root.addWidget(title)

        form = QtWidgets.QFormLayout()
        form.setLabelAlignment(QtCore.Qt.AlignRight)
        root.addLayout(form)

        self._name_edit = QtWidgets.QLineEdit(self)
        self._name_edit.setPlaceholderText("Имя ноды…")
        self._name_edit.editingFinished.connect(self._apply_name)
        form.addRow("Name:", self._name_edit)

        self._class_lbl = QtWidgets.QLabel("")
        self._class_lbl.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
        form.addRow("Class:", self._class_lbl)

        self._category_lbl = QtWidgets.QLabel("")
        self._category_lbl.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
        form.addRow("Category:", self._category_lbl)

        self._id_lbl = QtWidgets.QLabel("")
        self._id_lbl.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
        form.addRow("ID:", self._id_lbl)

        clr_row = QtWidgets.QHBoxLayout()
        self._color_btn = QtWidgets.QPushButton("Цвет…")
        self._color_btn.clicked.connect(self._pick_color)
        clr_row.addWidget(self._color_btn, 0)
        clr_row.addStretch(1)
        form.addRow("Color:", clr_row)

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

        self._empty_lbl = QtWidgets.QLabel("нет выбранной ноды")
        self._empty_lbl.setAlignment(QtCore.Qt.AlignCenter)
        self._empty_lbl.setStyleSheet("color:#aaaaaa;")
        root.addWidget(self._empty_lbl)

        self._update_enabled(False)
        self._hook_graph_events()
        self.refresh_from_selection()

    def bind_graph(self, graph) -> None:
        self._graph = graph
        self._hook_graph_events()
        self.refresh_from_selection()

    def _hook_graph_events(self) -> None:
        g = self._graph
        if not g or getattr(self, "_graph_hooks_installed", False):
            return
        try:
            g.node_selection_changed.connect(self.refresh_from_selection)
            g.node_deleted.connect(self.refresh_from_selection)
            g.node_created.connect(self.refresh_from_selection)
            # Добавим подписку на изменение имени, чтобы обновлять инспектор
            if hasattr(g, 'node_renamed'):
                g.node_renamed.connect(lambda node, name: self.refresh_from_selection())
        except Exception:
            pass
        self._graph_hooks_installed = True

    def _update_enabled(self, enabled: bool) -> None:
        for w in (self._name_edit, self._color_btn, self._inputs, self._outputs):
            w.setEnabled(enabled)
        self._empty_lbl.setVisible(not enabled)

    def refresh_from_selection(self) -> None:
        g = self._graph
        sel = g.selected_nodes() if g else []

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

        self._name_edit.setText(n.name())
        self._class_lbl.setText(n.__class__.__name__)
        self._category_lbl.setText(getattr(n, '__identifier__', ''))
        self._id_lbl.setText(n.id)

        color_tuple = n.color()
        if isinstance(color_tuple, (list, tuple)) and len(color_tuple) >= 3:
            self._apply_color_btn(f"rgb({color_tuple[0]}, {color_tuple[1]}, {color_tuple[2]})")

        self._fill_ports(n)
        self._update_enabled(True)

    def _apply_name(self) -> None:
        if self._node:
            self._node.set_name(self._name_edit.text().strip())

    def _apply_color_btn(self, css_color_str: str) -> None:
        self._color_btn.setStyleSheet(f"background-color:{css_color_str};")

    def _pick_color(self) -> None:
        n = self._node
        if not n: return

        # Получаем текущий цвет в формате QColor для диалога
        current_color_tuple = n.color()
        initial_color = QtGui.QColor(*current_color_tuple)

        # Открываем диалог выбора цвета
        new_color_obj = QtWidgets.QColorDialog.getColor(initial_color, self, "Цвет ноды")

        if not new_color_obj.isValid():
            return

        # --- НАЧАЛО ИСПРАВЛЕНИЯ ---
        # Преобразуем объект QColor в кортеж (r, g, b)
        new_color_tuple = (new_color_obj.red(), new_color_obj.green(), new_color_obj.blue())

        # Устанавливаем цвет ноды, передавая кортеж, а не объект QColor
        n.set_color(*new_color_tuple)
        # --- КОНЕЦ ИСПРАВЛЕНИЯ ---

        # Обновляем цвет кнопки в инспекторе
        self._apply_color_btn(new_color_obj.name())

    def _fill_ports(self, n):
        self._inputs.clear()
        self._outputs.clear()

        def _make_item(p, is_input):
            conns = p.connected_ports()
            name = p.name()
            item_text = f"{name} [{len(conns)}]"
            it = QtWidgets.QListWidgetItem(item_text)
            if conns:
                tips = [f"{other.node().name()}:{other.name()}" for other in conns]
                it.setToolTip("\n".join(tips))
            return it

        # --- НАЧАЛО ИСПРАВЛЕНИЯ ---
        inputs = n.inputs()
        if inputs:
            for p in inputs.values():
                self._inputs.addItem(_make_item(p, True))

        outputs = n.outputs()
        if outputs:
            for p in outputs.values():
                self._outputs.addItem(_make_item(p, False))


def make_node_inspector_widget(main_window: QtWidgets.QMainWindow) -> QtWidgets.QWidget:
    w = NodeInspectorWidget(main_window)
    return w