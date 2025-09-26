# ==============================================================================
# Файл: editor/custom_graph.py
# Назначение: Кастомный граф с собственным контекстным меню,
#             быстрыми действиями (Backdrop) и устойчивой группировкой нод.
# Версия: 2.1
# ==============================================================================

from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any, Dict, Iterable, List, Optional, Tuple

from PySide6 import QtCore, QtWidgets
from NodeGraphQt import NodeGraph

logger = logging.getLogger(__name__)

# Ремап категорий (исходное -> отображаемое). None = скрыть.
CATEGORY_REMAP: Dict[str, Optional[str]] = {
    "generator.noises": "Ландшафт.Шумы",
    "Noise": "Ландшафт.Шумы",
}
# Явно скрываемые ноды по имени
HIDE_NODE_BY_NAME = {"Backdrop"}


class CustomNodeGraph(NodeGraph):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._context_menu_target = None          # <- добавили
        self._context_menu_connected = False      # <- добавили
        self._install_context_menu()

    # ---------- контекстное меню ----------
    def enable_context_menu(self) -> None:
        self._install_context_menu()

    def _get_viewer(self) -> Optional[QtWidgets.QGraphicsView]:
        # Ищем настоящий QGraphicsView внутри NodeGraphWidget
        return self.widget.findChild(QtWidgets.QGraphicsView)

    def _install_context_menu(self) -> None:
        viewer = self._get_viewer()
        target = viewer.viewport() if viewer else self.widget  # цепляемся к viewport'у QGraphicsView

        target.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.CustomContextMenu)

        # отключаемся только если МЫ раньше подключались и цель изменилась
        if self._context_menu_connected and self._context_menu_target is not None and self._context_menu_target is not target:
            try:
                self._context_menu_target.customContextMenuRequested.disconnect(self._on_custom_context_menu)
            except Exception:
                pass

        # подключаемся только если ещё не были подключены или цель изменилась
        if (not self._context_menu_connected) or (self._context_menu_target is not target):
            target.customContextMenuRequested.connect(
                self._on_custom_context_menu
                # можно добавить UniqueConnection, но с флагами выше это не требуется
                # , QtCore.Qt.ConnectionType.UniqueConnection
            )
            self._context_menu_connected = True
            self._context_menu_target = target

    # совместимость со старым вызовом из некоторых версий NodeGraphQt
    def _on_show_context_menu(self, pos):
        viewer = self._get_viewer()
        if viewer:
            if isinstance(pos, QtCore.QPointF):
                vp = viewer.mapFromScene(pos)
            else:
                vp = pos
        else:
            vp = pos if isinstance(pos, QtCore.QPoint) else QtCore.QPoint(int(pos.x()), int(pos.y()))
        self._on_custom_context_menu(vp)

    def _on_custom_context_menu(self, pos: QtCore.QPoint) -> None:
        viewer = self._get_viewer()
        # pos – координаты **viewport'а**, если мы повесились на него (как задумано)
        if viewer and self._context_menu_target is viewer.viewport():
            scene_pos = viewer.mapToScene(pos)
            global_pos = viewer.viewport().mapToGlobal(pos)
        else:
            # fallback: пришли координаты узла-обёртки, перенесём их в систему координат viewer
            if viewer:
                vp = viewer.mapFrom(self.widget, pos)
                scene_pos = viewer.mapToScene(vp)
                global_pos = self.widget.mapToGlobal(pos)
            else:
                scene_pos = QtCore.QPointF(pos)
                global_pos = self.widget.mapToGlobal(pos)

        menu = QtWidgets.QMenu(self.widget)

        # быстрые действия
        selected = self.selected_nodes()
        if selected:
            act_del = menu.addAction("Удалить выбранные")
            act_del.triggered.connect(lambda _checked=False: self.delete_nodes(self.selected_nodes()))
            menu.addSeparator()

        act_group = menu.addAction("Сгруппировать бэкдропом (Ctrl+G)")
        act_group.setEnabled(bool(selected))
        act_group.triggered.connect(lambda _checked=False: self._create_backdrop_around_selection())

        act_empty = menu.addAction("Пустой бэкдроп")
        act_empty.triggered.connect(lambda _checked=False, sp=scene_pos: self._create_backdrop_at(sp))
        menu.addSeparator()

        # дерево нод
        grouped = self._collect_nodes_grouped()
        self._build_nodes_menu(menu, grouped)

        menu.exec_(global_pos)

    def show_context_menu_at(self, pos: QtCore.QPoint, source_widget: QtWidgets.QWidget) -> None:
        """
        Показать наше контекстное меню в точке pos (координаты source_widget).
        Работает и если source_widget — viewport QGraphicsView, и если это wrapper-виджет.
        """
        viewer = self._get_viewer()
        if viewer is None:
            return

        # pos -> scene/global
        if source_widget is viewer.viewport():
            scene_pos = viewer.mapToScene(pos)
            global_pos = source_widget.mapToGlobal(pos)
        else:
            vp = viewer.mapFrom(source_widget, pos)
            scene_pos = viewer.mapToScene(vp)
            global_pos = source_widget.mapToGlobal(pos)

        menu = QtWidgets.QMenu(self.widget)

        # быстрые действия
        selected = self.selected_nodes()
        if selected:
            act_del = menu.addAction("Удалить выбранные")
            act_del.triggered.connect(lambda _checked=False: self.delete_nodes(self.selected_nodes()))
            menu.addSeparator()

        act_group = menu.addAction("Сгруппировать бэкдропом (Ctrl+G)")
        act_group.setEnabled(bool(selected))
        act_group.triggered.connect(lambda _checked=False: self._create_backdrop_around_selection())

        act_empty = menu.addAction("Пустой бэкдроп")
        act_empty.triggered.connect(lambda _checked=False, sp=scene_pos: self._create_backdrop_at(sp))
        menu.addSeparator()

        # дерево нод
        grouped = self._collect_nodes_grouped()
        self._build_nodes_menu(menu, grouped)

        menu.exec_(global_pos)

    # ---------- нормализация registered_nodes() ----------
    def _iter_registered(self) -> Iterable[Tuple[Optional[str], Any]]:
        """
        Поддерживаем:
          - dict {node_id: class}
          - list [class, ...]
          - list [(node_id, class), ...]
          - list [node_id:str, ...]
        Возвращаем последовательность (node_id|None, class|str).
        """
        reg = self.registered_nodes()
        if isinstance(reg, dict):
            return list(reg.items())

        out: List[Tuple[Optional[str], Any]] = []
        if isinstance(reg, list):
            for el in reg:
                if isinstance(el, tuple) and len(el) == 2:
                    out.append((el[0], el[1]))
                elif isinstance(el, str):
                    out.append((el, el))          # знаем только id
                else:
                    out.append((None, el))        # знаем только класс
        return out

    def _display_name(self, cls_or_str: Any) -> str:
        if isinstance(cls_or_str, str):
            return cls_or_str.rsplit(".", 1)[-1] or cls_or_str
        return getattr(cls_or_str, "NODE_NAME", getattr(cls_or_str, "__name__", "Node"))

    def _identifier(self, cls_or_str: Any) -> str:
        if isinstance(cls_or_str, str):
            return cls_or_str.rsplit(".", 1)[0] if "." in cls_or_str else "Прочее"
        return getattr(cls_or_str, "__identifier__", "Прочее")

    def _friendly_category(self, ident: str) -> Optional[str]:
        if not ident:
            ident = "Прочее"
        if ident.startswith("nodeGraphQt"):
            return None
        if ident in CATEGORY_REMAP:
            return CATEGORY_REMAP[ident]
        return ident

    def _collect_nodes_grouped(self) -> Dict[str, List[Tuple[str, List[str]]]]:
        """
        Результат:
          { "Категория": [(display_name, [create_tokens...]), ...], ... }
        где create_tokens — строки для create_node (NODE_NAME, id, type).
        """
        grouped: Dict[str, List[Tuple[str, List[str]]]] = defaultdict(list)

        for node_id, cls_or_str in self._iter_registered():
            name = self._display_name(cls_or_str)
            ident = self._identifier(cls_or_str)

            if name in HIDE_NODE_BY_NAME:
                continue

            cat = self._friendly_category(ident)
            if cat is None:
                continue

            tokens: List[str] = []
            if not isinstance(cls_or_str, str):
                tokens.append(name)  # по NODE_NAME
                cls_name = getattr(cls_or_str, "__name__", None)
                if ident and cls_name:
                    tokens.append(f"{ident}.{cls_name}")  # по типу
            if isinstance(node_id, str):
                tokens.append(node_id)  # по id

            # убираем дубли, сохраняя порядок
            seen = set()
            uniq_tokens = []
            for t in tokens:
                if t and t not in seen:
                    seen.add(t)
                    uniq_tokens.append(t)

            grouped[cat].append((name, uniq_tokens))

        # сортировки
        grouped = dict(sorted(grouped.items(), key=lambda kv: kv[0].lower()))
        for k in grouped:
            grouped[k].sort(key=lambda p: p[0].lower())
        return grouped

    def _build_nodes_menu(
        self,
        parent_menu: QtWidgets.QMenu,
        nodes_by_category: Dict[str, List[Tuple[str, List[str]]]],
    ) -> None:
        """
        Рекурсивно строим меню из путей категорий ('.' — разделитель).
        """
        subtrees: Dict[str, Dict[str, List[Tuple[str, List[str]]]]] = defaultdict(dict)
        terminal: Dict[str, List[Tuple[str, List[str]]]] = {}

        for path, items in nodes_by_category.items():
            if "." in path:
                head, tail = path.split(".", 1)
                subtrees.setdefault(head, {})
                subtrees[head][tail] = items
            else:
                terminal[path] = items

        # подменю
        for head in sorted(subtrees.keys(), key=lambda s: s.lower()):
            m = parent_menu.addMenu(head)
            self._build_nodes_menu(m, subtrees[head])

        # финальные категории (секция + действия)
        for cat in sorted(terminal.keys(), key=lambda s: s.lower()):
            parent_menu.addSection(cat.replace(".", " / "))
            for display_name, tokens in terminal[cat]:
                act = parent_menu.addAction(display_name)

                def _make(_checked=False, tokens=tokens):
                    for t in tokens:
                        try:
                            self.create_node(t)
                            return
                        except Exception:
                            continue
                    logger.warning("Не удалось создать ноду '%s' (tokens=%s)", display_name, tokens)

                act.triggered.connect(_make)

    # ---------- быстрые действия: Backdrop ----------
    def _create_backdrop_around_selection(self, padding: int = 30, title: str = "Группа") -> None:
        try:
            from NodeGraphQt import BackdropNode
        except Exception:
            BackdropNode = None

        nodes = self.selected_nodes()
        if BackdropNode is not None:
            nodes = [n for n in nodes if not isinstance(n, BackdropNode)]
        if not nodes:
            return

        bd = None
        for token in ("nodeGraphQt.nodes.Backdrop",):
            try:
                bd = self.create_node(token)
                break
            except Exception:
                pass
        if bd is None and BackdropNode is not None:
            try:
                bd = self.create_node(f"{BackdropNode.__module__}.{BackdropNode.__name__}")
            except Exception:
                bd = None
        if bd is None:
            return

        if hasattr(bd, "set_child_nodes"):
            try:
                bd.set_child_nodes(nodes)
                if hasattr(bd, "set_text"):
                    bd.set_text(title)
                return
            except Exception:
                pass

        def _pos(n):
            try:
                return n.pos()
            except Exception:
                return (0, 0)

        def _w(n):
            v = getattr(n, "width", None); v = v() if callable(v) else v
            if v is None: v = getattr(n, "_width", None)
            return v if v is not None else 160

        def _h(n):
            v = getattr(n, "height", None); v = v() if callable(v) else v
            if v is None: v = getattr(n, "_height", None)
            return v if v is not None else 80

        xs, ys, x2, y2 = [], [], [], []
        for n in nodes:
            x, y = _pos(n)
            xs.append(x); ys.append(y)
            x2.append(x + _w(n)); y2.append(y + _h(n))

        x = min(xs) - padding
        y = min(ys) - padding
        W = (max(x2) - min(xs)) + padding * 2
        H = (max(y2) - min(ys)) + padding * 2

        if hasattr(bd, "set_pos"):   bd.set_pos(x, y)
        if hasattr(bd, "set_size"):  bd.set_size(W, H)
        else:
            if hasattr(bd, "set_width"):  bd.set_width(W)
            if hasattr(bd, "set_height"): bd.set_height(H)
        if hasattr(bd, "set_text"):  bd.set_text(title)

    def _create_backdrop_at(self, scene_pos: QtCore.QPointF, size=(600, 300), title: str = "Группа") -> None:
        bd = None
        for token in ("nodeGraphQt.nodes.Backdrop",):
            try:
                bd = self.create_node(token)
                break
            except Exception:
                pass
        if bd is None:
            try:
                from NodeGraphQt import BackdropNode
                bd = self.create_node(f"{BackdropNode.__module__}.{BackdropNode.__name__}")
            except Exception:
                bd = None
        if bd is None:
            return

        if hasattr(bd, "set_pos"):   bd.set_pos(scene_pos.x(), scene_pos.y())
        if hasattr(bd, "set_size"):  bd.set_size(*size)
        else:
            if hasattr(bd, "set_width"):  bd.set_width(size[0])
            if hasattr(bd, "set_height"): bd.set_height(size[1])
        if hasattr(bd, "set_text"):  bd.set_text(title)
