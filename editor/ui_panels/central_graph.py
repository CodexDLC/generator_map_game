# editor/ui/central_graph.py
from typing import cast
import logging
from PySide6 import QtWidgets, QtCore, QtGui

from ..custom_graph import CustomNodeGraph
from ..nodes.node_registry import register_all_nodes

logger = logging.getLogger(__name__)

def setup_central_graph_ui(mw) -> None:
    """
    Строит центральный UI: превью + граф. Вешает Delete/Backspace на канву графа,
    фиксирует drag-режим и правильно управляет фокусом.
    """
    # 0) Граф
    mw.graph = CustomNodeGraph()
    register_all_nodes(mw.graph)

    graph_widget = mw.graph.widget
    graph_widget.setObjectName("Основной граф 'Ландшафт'")
    graph_widget.setFocusPolicy(QtCore.Qt.FocusPolicy.StrongFocus)

    # 1) Превью не должно воровать клавиатуру
    mw.preview_widget.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)

    # 2) Сплиттер: превью сверху, граф снизу
    splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Vertical)
    splitter.addWidget(mw.preview_widget)
    splitter.addWidget(cast(QtWidgets.QWidget, graph_widget))
    splitter.setSizes([400, 600])
    mw.setCentralWidget(splitter)

    # 3) Реальный QGraphicsView внутри graph_widget
    view = graph_widget.findChild(QtWidgets.QGraphicsView) or graph_widget
    if isinstance(view, QtWidgets.QGraphicsView):
        view.setDragMode(QtWidgets.QGraphicsView.RubberBandDrag)

    # 4) Шорткаты удаления на канву (один раз)
    if not getattr(view, "_delete_shortcuts_installed", False):
        def _do_delete():
            sel = [n.name() for n in mw.graph.selected_nodes()]
            logger.debug("[DELETE] shortcut fired; selected=%s", sel)
            if sel:
                mw.graph.delete_nodes(mw.graph.selected_nodes())

        del_sc = QtGui.QShortcut(QtGui.QKeySequence(QtCore.Qt.Key_Delete), view)
        del_sc.setContext(QtCore.Qt.ShortcutContext.WidgetShortcut)
        del_sc.activated.connect(_do_delete)

        back_sc = QtGui.QShortcut(QtGui.QKeySequence(QtCore.Qt.Key_Backspace), view)
        back_sc.setContext(QtCore.Qt.ShortcutContext.WidgetShortcut)
        back_sc.activated.connect(_do_delete)

        # Диагностика клавиш — можно удалить позже
        class _KeySpy(QtCore.QObject):
            def eventFilter(self, o, e):
                if e.type() == QtCore.QEvent.Type.KeyPress:
                    try:
                        key_name = QtCore.Qt.Key(e.key()).name
                    except Exception:
                        key_name = str(e.key())
                    logger.debug("[KEY on VIEW] %s (focus=%s)",
                                 key_name, QtWidgets.QApplication.focusWidget())
                return super().eventFilter(o, e)

        view.installEventFilter(_KeySpy(view))
        view._delete_shortcuts_installed = True

    # 5) Фокус на канву — уже после сборки центрального виджета
    view.setFocusPolicy(QtCore.Qt.FocusPolicy.StrongFocus)
    QtCore.QTimer.singleShot(0, lambda: view.setFocus(QtCore.Qt.FocusReason.ActiveWindowFocusReason))
