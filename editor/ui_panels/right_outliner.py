# ==============================================================================
# Файл: editor/ui_panels/right_outliner.py
# ВЕРСИЯ 3.1 (HOTFIX): Восстановлена связь с панелью свойств.
# - Теперь принудительно вызывает сигнал selection_changed через графа.
# ==============================================================================

from __future__ import annotations
from typing import Dict, Any, List, Optional
from PySide6 import QtWidgets, QtCore, QtGui

from NodeGraphQt import BaseNode
from editor.custom_graph import CustomNodeGraph # Используем для аннотации типов


class RightOutlinerWidget(QtWidgets.QWidget):
    apply_clicked = QtCore.Signal()  # наружу: запуск вычисления

    def __init__(self, main_window: QtWidgets.QMainWindow):
        super().__init__(parent=main_window)
        self.setObjectName("RightOutliner")
        self._mw = main_window
        self._graph: Optional[CustomNodeGraph] = None
        self._sync_guard = False

        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(6)

        title = QtWidgets.QLabel("Outliner")
        title.setStyleSheet("font-weight: bold;")
        lay.addWidget(title)

        self._search_edit = QtWidgets.QLineEdit(self)
        self._search_edit.setPlaceholderText("Фильтр по имени ноды…")
        self._search_edit.textChanged.connect(self._filter_tree)
        lay.addWidget(self._search_edit)

        self._tree = QtWidgets.QTreeWidget(self)
        self._tree.setObjectName("OutlinerTree")
        self._tree.setHeaderHidden(True)
        self._tree.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        lay.addWidget(self._tree, 1)

        self._tree.currentItemChanged.connect(self._on_tree_item_changed)

        line = QtWidgets.QFrame(self)
        line.setFrameShape(QtWidgets.QFrame.HLine)
        line.setFrameShadow(QtWidgets.QFrame.Sunken)
        lay.addWidget(line)

        self.apply_button = QtWidgets.QPushButton("APPLY", self)
        self.apply_button.setObjectName("apply_button_right_outliner")
        self.apply_button.setFixedHeight(40)
        self.apply_button.clicked.connect(self.apply_clicked.emit)
        lay.addWidget(self.apply_button)

        self._node_id_to_item: Dict[str, QtWidgets.QTreeWidgetItem] = {}
        self._hooks_installed = False

    def set_busy(self, busy: bool) -> None:
        self.apply_button.setEnabled(not busy)
        self.apply_button.setText("⏳ APPLY" if busy else "APPLY")

    def bind_graph(self, graph: CustomNodeGraph) -> None:
        if self._graph is graph:
            return

        if self._graph:
            try: self._graph.selection_changed.disconnect(self._sync_from_graph_selection) 
            except: pass
            try: self._graph.node_renamed.disconnect(self._on_node_name_changed) 
            except: pass
            try: self._graph.structure_changed.disconnect(self.refresh) 
            except: pass

        self._graph = graph
        self.refresh()

        if self._hooks_installed or graph is None:
            return

        graph.selection_changed.connect(self._sync_from_graph_selection)
        graph.node_renamed.connect(self._on_node_name_changed)
        graph.structure_changed.connect(self.refresh)

        self._hooks_installed = True

    def refresh(self) -> None:
        self._tree.clear()
        self._node_id_to_item.clear()
        if self._graph is None:
            return

        root = QtWidgets.QTreeWidgetItem(["Граф"])
        self._tree.addTopLevelItem(root)
        group_outputs = QtWidgets.QTreeWidgetItem(["Выходы"])
        group_others = QtWidgets.QTreeWidgetItem(["Прочие ноды"])
        root.addChild(group_outputs)
        root.addChild(group_others)

        nodes: List[BaseNode] = self._graph.all_nodes()

        for n in nodes:
            name = n.name()
            node_id = n.id
            it = QtWidgets.QTreeWidgetItem([name])
            it.setData(0, QtCore.Qt.UserRole, node_id)
            self._node_id_to_item[node_id] = it
            cls_name = n.__class__.__name__.lower()
            (group_outputs if cls_name.startswith("output") else group_others).addChild(it)

        self._tree.expandAll()
        self._apply_filter_to_tree(self._search_edit.text().strip())
        if self._graph:
            self._sync_from_graph_selection(self._graph.selected_nodes())

    def _on_tree_item_changed(self, item: QtWidgets.QTreeWidgetItem, *_):
        if self._sync_guard or self._graph is None or item is None:
            return

        node_id = item.data(0, QtCore.Qt.UserRole)
        if not node_id:
            return

        self._sync_guard = True
        try:
            node_to_select = self._graph.get_node_by_id(node_id)
            if node_to_select:
                self._graph.clear_selection()
                node_to_select.set_selected(True)

                # --- HOTFIX: Принудительно сообщаем всем об изменении выделения ---
                self._graph.force_emit_selection_changed()
                # ----------------------------------------------------------------

                view = self._graph.widget.findChild(QtWidgets.QGraphicsView)
                if view and hasattr(node_to_select, 'graphics_item'):
                    gi = node_to_select.graphics_item()
                    if gi:
                        view.ensureVisible(gi)
        finally:
            self._sync_guard = False

    @QtCore.Slot(list)
    def _sync_from_graph_selection(self, selected_nodes: list) -> None:
        if self._graph is None or self._sync_guard:
            return

        self._sync_guard = True
        try:
            if not selected_nodes:
                self._tree.clearSelection()
                self._tree.setCurrentItem(None)
                return

            node = selected_nodes[0]
            item = self._node_id_to_item.get(node.id)
            if item and self._tree.currentItem() is not item:
                self._tree.setCurrentItem(item)
        finally:
            self._sync_guard = False

    def _filter_tree(self, text: str) -> None:
        self._apply_filter_to_tree(text.strip())

    def _apply_filter_to_tree(self, text: str) -> None:
        text = (text or "").lower()
        root = self._tree.invisibleRootItem()

        for i in range(root.childCount()):
            cat_item = root.child(i)
            child_matches = False
            for j in range(cat_item.childCount()):
                node_item = cat_item.child(j)
                name_matches = text in node_item.text(0).lower()
                node_item.setHidden(not name_matches)
                if name_matches:
                    child_matches = True
            cat_item.setHidden(not child_matches)

    @QtCore.Slot(object, str)
    def _on_node_name_changed(self, node: BaseNode, name: str):
        item = self._node_id_to_item.get(node.id)
        if item:
            item.setText(0, name)
