# ==============================================================================
# Файл: editor/ui_panels/nodes_palette_panel.py
# ВЕРСИЯ 3.1 (HOTFIX): Исправлен конструктор в соответствии с API PySide6.
# ==============================================================================

from __future__ import annotations
import logging
from typing import Dict, List, Tuple

from PySide6 import QtWidgets, QtCore, QtGui

from editor.custom_graph import CustomNodeGraph

logger = logging.getLogger(__name__)


class _PaletteList(QtWidgets.QTreeWidget):
    """Дерево нодов в палитре. Поддерживает Drag&Drop."""
    # Этот класс не требует изменений
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setHeaderHidden(True)
        self.setDragEnabled(True)
        self.setObjectName("NodesPaletteTree")

    def startDrag(self, supportedActions):
        item = self.currentItem()
        if not item or item.childCount() > 0: # Нельзя перетаскивать категории
            return
        node_id = item.data(0, QtCore.Qt.UserRole)
        if not node_id:
            return
        drag = QtGui.QDrag(self)
        mime = QtCore.QMimeData()
        mime.setData("application/x-node-id", str(node_id).encode("utf-8"))
        drag.setMimeData(mime)
        drag.exec(QtCore.Qt.CopyAction)


class NodesPaletteWidget(QtWidgets.QWidget):
    """Встраиваемая палитра нодов, получающая данные от графа."""

    # РЕФАКТОРИНГ: Конструктор теперь принимает только `parent`
    def __init__(self, parent: QtWidgets.QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("LeftNodesPalette")

        self._graph: CustomNodeGraph | None = None
        self._spawn_guard = False
        self._node_catalogue: Dict[str, List[Tuple[str, str]]] = {}

        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(6)

        self._search = QtWidgets.QLineEdit(self)
        self._search.setPlaceholderText("Поиск ноды…")
        self._search.textChanged.connect(self.repaint_list)
        root.addWidget(self._search)

        self._list = _PaletteList(self)
        self._list.itemActivated.connect(self._on_item_activated)
        root.addWidget(self._list, 1)

    def bind_graph(self, graph: CustomNodeGraph):
        """Получает граф, запрашивает у него каталог нод и строит список."""
        self._graph = graph
        self._node_catalogue = self._graph.get_node_catalogue()
        self.repaint_list()

    def repaint_list(self):
        """Перерисовывает дерево на основе каталога и текста в поиске."""
        self._list.clear()
        search_text = self._search.text().strip().lower()

        for category, nodes in self._node_catalogue.items():
            filtered_nodes = [
                (name, node_id) for name, node_id in nodes
                if not search_text or search_text in name.lower()
            ]

            if filtered_nodes:
                cat_item = QtWidgets.QTreeWidgetItem([category])
                self._list.addTopLevelItem(cat_item)
                for name, node_id in filtered_nodes:
                    node_item = QtWidgets.QTreeWidgetItem([name])
                    node_item.setData(0, QtCore.Qt.UserRole, node_id)
                    node_item.setToolTip(0, f"ID: {node_id}")
                    cat_item.addChild(node_item)

        if search_text:
            self._list.expandAll()
        else:
            self._list.collapseAll()

    @QtCore.Slot(QtWidgets.QTreeWidgetItem, int)
    def _on_item_activated(self, item: QtWidgets.QTreeWidgetItem, column: int):
        node_id = item.data(0, QtCore.Qt.UserRole)
        if node_id and self._graph:
            self._spawn_in_graph(node_id)

    def _spawn_in_graph(self, node_id: str):
        if self._spawn_guard or self._graph is None:
            return
        self._spawn_guard = True
        try:
            view = self._graph.widget.findChild(QtWidgets.QGraphicsView)
            scene_pos = None
            if view:
                global_pos = QtGui.QCursor.pos()
                view_pos = view.mapFromGlobal(global_pos)
                scene_pos_qpoint = view.mapToScene(view_pos)
                scene_pos = (scene_pos_qpoint.x(), scene_pos_qpoint.y())

            if scene_pos is None and view:
                r = view.viewport().rect()
                center_scene_pos = view.mapToScene(r.center())
                scene_pos = (center_scene_pos.x(), center_scene_pos.y())

            self._graph.create_node(node_id, pos=scene_pos)

        finally:
            QtCore.QTimer.singleShot(0, lambda: setattr(self, "_spawn_guard", False))
