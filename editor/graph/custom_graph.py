# ==============================================================================
# Файл: editor/custom_graph.py
# ВЕРСИЯ 5.3 (HOTFIX): Добавлен метод для принудительной отправки сигнала.
# - Новый метод force_emit_selection_changed() позволяет аутлайнеру
#   сообщать остальному UI об изменении выделения.
# ==============================================================================

from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple

from PySide6 import QtCore, QtWidgets, QtGui
from NodeGraphQt import NodeGraph, BaseNode

logger = logging.getLogger(__name__)


class CustomNodeGraph(NodeGraph):
    """
    Кастомный граф, который предоставляет стабильный API для остального приложения,
    скрывая детали реализации нижележащей библиотеки NodeGraphQt.
    """

    selection_changed = QtCore.Signal(list)
    structure_changed = QtCore.Signal()
    node_renamed = QtCore.Signal(object, str)

    def __init__(self, parent=None):
        super().__init__(parent)

    def finalize_setup(self):
        """Вызывается из MainWindow после того, как виджет графа встроен в UI."""
        self._install_context_menu()
        self._install_drag_and_drop()
        self._install_shortcuts()
        self._connect_internal_signals()

    def _connect_internal_signals(self):
        """Подключает "грязные" сигналы библиотеки к нашим чистым слотам."""
        self.node_created.connect(self._on_structure_changed)
        self.nodes_deleted.connect(self._on_structure_changed)
        self.port_connected.connect(self._on_structure_changed)
        self.port_disconnected.connect(self._on_structure_changed)
        self.node_selection_changed.connect(self._on_selection_changed)
        self.property_changed.connect(self._on_property_changed)

    # --- РЕФАКТОРИНГ: Новый публичный метод для принудительной отправки сигнала ---
    def force_emit_selection_changed(self):
        """
        Принудительно излучает сигнал `selection_changed` с текущим выделением.
        Это необходимо для UI-элементов (как аутлайнер), которые меняют
        выделение программно, не вызывая стандартный сигнал библиотеки.
        """
        self.selection_changed.emit(self.selected_nodes())

    # --- Слоты-адаптеры ---
    @QtCore.Slot(list, list)
    def _on_selection_changed(self, selected_nodes: list, deselected_nodes: list):
        self.selection_changed.emit(selected_nodes)

    @QtCore.Slot(object, str, object)
    def _on_property_changed(self, node: BaseNode, prop_name: str, prop_value: Any):
        if prop_name == 'name':
            self.node_renamed.emit(node, prop_value)

    @QtCore.Slot()
    def _on_structure_changed(self, *args, **kwargs):
        self.structure_changed.emit()

    def get_node_catalogue(self) -> Dict[str, List[Tuple[str, str]]]:
        registered_nodes = self.node_factory.nodes
        grouped: Dict[str, List[Tuple[str, str]]] = defaultdict(list)
        for node_id, node_class in registered_nodes.items():
            if node_class is BaseNode or node_class.__name__ == 'BackdropNode':
                continue
            display_name = getattr(node_class, 'NODE_NAME', node_class.__name__)
            category = getattr(node_class, '__identifier__', 'Прочее')
            if not category:
                 continue
            grouped[category].append((display_name, node_id))
        for cat_items in grouped.values():
            cat_items.sort(key=lambda x: x[0].lower())
        return dict(sorted(grouped.items(), key=lambda x: x[0].lower()))

    def _get_viewer(self) -> Optional[QtWidgets.QGraphicsView]:
        return self.widget.findChild(QtWidgets.QGraphicsView)

    def _install_context_menu(self) -> None:
        viewer = self._get_viewer()
        if not viewer:
            return
        target = viewer.viewport()
        target.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.CustomContextMenu)
        target.customContextMenuRequested.connect(self._on_custom_context_menu)

    def _on_custom_context_menu(self, pos: QtCore.QPoint) -> None:
        viewer = self._get_viewer()
        if not viewer:
            return
        scene_pos = viewer.mapToScene(pos)
        global_pos = viewer.viewport().mapToGlobal(pos)
        menu = QtWidgets.QMenu(self.widget)
        node_catalogue = self.get_node_catalogue()
        self._build_nodes_menu(menu, node_catalogue, scene_pos)
        menu.addSeparator()
        selected = self.selected_nodes()
        if selected:
            act_del = menu.addAction("Удалить выбранные")
            act_del.triggered.connect(lambda: self.delete_nodes(self.selected_nodes()))
        act_group = menu.addAction("Сгруппировать бэкдропом (Ctrl+G)")
        act_group.setEnabled(bool(selected))
        act_group.triggered.connect(lambda: self._create_backdrop_around_selection())
        menu.exec_(global_pos)

    def _build_nodes_menu(self, parent_menu: QtWidgets.QMenu, nodes_by_category: dict, scene_pos: QtCore.QPointF) -> None:
        for category, nodes in nodes_by_category.items():
            m = parent_menu.addMenu(category)
            for display_name, node_id in nodes:
                act = m.addAction(display_name)
                def _create_node_at_pos(_checked=False, nid=node_id, pos=scene_pos):
                    try:
                        self.create_node(nid, pos=(pos.x(), pos.y()))
                    except Exception as e:
                        logger.error(f"Не удалось создать ноду '{display_name}' по ID '{nid}': {e}")
                act.triggered.connect(_create_node_at_pos)

    def _install_drag_and_drop(self):
        viewer = self._get_viewer()
        if not viewer:
            return
        viewer.setAcceptDrops(True)
        dnd_filter = _DragDropFilter(self, viewer)
        viewer.installEventFilter(dnd_filter)
        setattr(viewer, "_dnd_filter", dnd_filter)

    def _install_shortcuts(self):
        viewer = self._get_viewer()
        if not viewer:
            return
        def _delete_selected_nodes():
            self.delete_nodes(self.selected_nodes())
        QtGui.QShortcut(QtGui.QKeySequence.StandardKey.Delete, viewer, _delete_selected_nodes)
        QtGui.QShortcut(QtGui.QKeySequence(QtCore.Qt.Key_Backspace), viewer, _delete_selected_nodes)

    def _create_backdrop_around_selection(self, padding: int = 30, title: str = "Группа") -> None:
        nodes = [n for n in self.selected_nodes() if n.__class__.__name__ != 'BackdropNode']
        if not nodes:
            return
        bd = self.create_node('nodeGraphQt.nodes.BackdropNode', name=title)
        if hasattr(bd, 'set_child_nodes'):
            bd.set_child_nodes(nodes)
        else:
            x_positions = [n.x_pos() for n in nodes]
            y_positions = [n.y_pos() for n in nodes]
            width = max(x_positions) - min(x_positions) + nodes[0].width() + padding * 2
            height = max(y_positions) - min(y_positions) + nodes[0].height() + padding * 2
            bd.set_pos(min(x_positions) - padding, min(y_positions) - padding)
            bd.set_width(width)
            bd.set_height(height)

class _DragDropFilter(QtCore.QObject):
    def __init__(self, graph: CustomNodeGraph, viewer: QtWidgets.QGraphicsView):
        super().__init__(viewer)
        self.graph = graph
        self.viewer = viewer

    def eventFilter(self, obj: QtCore.QObject, event: QtCore.QEvent) -> bool:
        if obj is not self.viewer:
            return False
        event_type = event.type()
        if event_type in (QtCore.QEvent.Type.DragEnter, QtCore.QEvent.Type.DragMove):
            mime_data = event.mimeData()
            if mime_data and mime_data.hasFormat("application/x-node-id"):
                event.acceptProposedAction()
                return True
        if event_type == QtCore.QEvent.Type.Drop:
            mime_data = event.mimeData()
            if mime_data and mime_data.hasFormat("application/x-node-id"):
                node_id = bytes(mime_data.data("application/x-node-id")).decode("utf-8")
                try:
                    drop_pos = event.position().toPoint() if hasattr(event, "position") else event.pos()
                    scene_pos = self.viewer.mapToScene(drop_pos)
                    self.graph.create_node(node_id, pos=(scene_pos.x(), scene_pos.y()))
                    event.acceptProposedAction()
                    return True
                except Exception as e:
                    logger.error(f"Failed to create node '{node_id}' from Drag&Drop: {e}")
        return False
