# ==============================================================================
# Файл: editor/ui_panels/nodes_palette_panel.py
# Кастомная палитра: поиск, скрытие служебных нод, устойчивость к dict/list/str
# ==============================================================================

from typing import cast, Dict, Iterable, Tuple, Type, Any
from PySide6 import QtWidgets, QtCore
import logging

logger = logging.getLogger(__name__)

# Ремап категорий: что пришло → как показывать. None = скрыть категорию целиком.
CATEGORY_REMAP: Dict[str, str | None] = {
    "nodeGraphQt.nodes": None,   # скрыть служебное
    "Backdrop": None,            # скрыть Backdrop из палитры
    "generator.noises": "Ландшафт.Шумы",
    "Noise": "Ландшафт.Шумы",
    # добавляй свои маппинги при необходимости
}

# Какие названия нод скрыть целиком
HIDE_NODE_BY_NAME = {"Backdrop"}


def _friendly_category(raw: str) -> str | None:
    if raw in CATEGORY_REMAP:
        return CATEGORY_REMAP[raw]
    return raw


def _safe_node_name(node_cls_or_str: Any) -> str:
    if isinstance(node_cls_or_str, str):
        # id вида "pkg.Class" → берем хвост для отображения
        return node_cls_or_str.split(".")[-1] or node_cls_or_str
    return getattr(node_cls_or_str, "NODE_NAME",
                   getattr(node_cls_or_str, "__name__", str(node_cls_or_str)))


def _safe_identifier(node_cls_or_str: Any) -> str:
    if isinstance(node_cls_or_str, str):
        # node_type вида "<identifier>.<ClassName>" -> берём левую часть как категорию
        return node_cls_or_str.rsplit(".", 1)[0] if "." in node_cls_or_str else "Прочее"
    return getattr(node_cls_or_str, "__identifier__", "Прочее")


class NodesPaletteWidget(QtWidgets.QWidget):
    def __init__(self, main_window, include_predicate=None):
        super().__init__(parent=main_window)
        self.main_window = main_window
        self._include_predicate = include_predicate or (lambda ident, name, node_id: True)

        self.search = QtWidgets.QLineEdit(placeholderText="Поиск нод…")
        self.search.textChanged.connect(self._rebuild)

        self.tree = QtWidgets.QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setExpandsOnDoubleClick(True)
        self.tree.itemActivated.connect(self._on_item_activated)

        def _toggle_if_category(item: QtWidgets.QTreeWidgetItem, _col: int):
            # Категории у нас без UserRole-данных
            if item.data(0, QtCore.Qt.UserRole) is None:
                item.setExpanded(not item.isExpanded())

        self.tree.itemClicked.connect(_toggle_if_category)

        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self.search)
        lay.addWidget(self.tree)

        self._rebuild()

    # ---------- сборка данных ----------
    def _iter_registered(self) -> Iterable[Tuple[str | None, Any]]:
        """
        Унифицируем разные варианты API:
        - dict {node_id: class}
        - list [class, ...]
        - list [(node_id, class), ...]
        - list [node_id:str, ...]
        Возвращаем последовательность пар (node_id|None, class|str).
        """
        graph = self.main_window.get_active_graph()
        if not graph:
            return []

        reg = graph.registered_nodes()

        # dict
        if isinstance(reg, dict):
            return list(reg.items())

        # list
        out: list[Tuple[str | None, Any]] = []
        for el in reg:
            if isinstance(el, tuple) and len(el) == 2:
                out.append((el[0], el[1]))
            elif isinstance(el, str):
                out.append((el, el))  # id известен, класса нет
            else:
                out.append((None, el))  # класс без id
        return out

    def _collect_nodes(self):
        """
        Возвращает словарь: {категория: [spec, ...]}
        где spec = {
            "name":  отображаемое имя,
            "by_name": токен создания по NODE_NAME (если есть),
            "by_id":  токен создания по node_id (если есть),
            "type":   "<identifier>.<ClassName>" (если можно построить),
            "ident":  исходный __identifier__ (для поиска/фильтра)
        }
        """
        by_cat: Dict[str, list[dict]] = {}

        for node_id, cls_or_str in self._iter_registered():
            name = _safe_node_name(cls_or_str)
            ident = _safe_identifier(cls_or_str)

            # 1) скрываем служебное (nodeGraphQt.*) и явные исключения (Backdrop)
            if isinstance(ident, str) and ident.startswith("nodeGraphQt"):
                continue
            if name in HIDE_NODE_BY_NAME:
                continue

            # 2) фильтр текущей вкладки (ident, name, node_id:str|None)
            node_id_str = node_id if isinstance(node_id, str) else None
            if not self._include_predicate(ident, name, node_id_str):
                continue

            # 3) человекочитаемая категория (ремап/скрытие)
            cat = _friendly_category(ident)
            if cat is None:
                continue

            # 4) подготовим все возможные «токены» для создания ноды
            by_name = name if not isinstance(cls_or_str, str) else None
            by_id = node_id_str
            type_token = None
            if not isinstance(cls_or_str, str):
                ident_attr = getattr(cls_or_str, "__identifier__", None)
                cls_name = getattr(cls_or_str, "__name__", None)
                if ident_attr and cls_name:
                    type_token = f"{ident_attr}.{cls_name}"

            spec = {
                "name": name,
                "by_name": by_name,
                "by_id": by_id,
                "type": type_token,
                "ident": ident,
            }
            by_cat.setdefault(cat, []).append(spec)

        # 5) сортировки: внутри категорий по имени, категории по алфавиту
        for cat, items in by_cat.items():
            items.sort(key=lambda s: s["name"].lower())
        by_cat_sorted = dict(sorted(by_cat.items(), key=lambda kv: kv[0].lower()))
        return by_cat_sorted

    def _rebuild(self):
        self.tree.clear()
        data = self._collect_nodes()
        q = self.search.text().strip().lower()
        total_nodes = 0

        # чтобы были видны стрелки разворота на всех стилях
        self.tree.setRootIsDecorated(True)

        for cat, items in data.items():
            # фильтр по поиску
            filtered = []
            for s in items:
                full = f"{s['name']} {s['ident']} {s.get('by_id', '')}".lower()
                if not q or q in full:
                    filtered.append(s)
            if not filtered:
                continue

            total_nodes += len(filtered)
            # подпишем количество нод в категории
            title = f"{cat.replace('.', ' / ')} ({len(filtered)})"
            cat_item = QtWidgets.QTreeWidgetItem([title])
            cat_item.setFlags(cat_item.flags() & ~QtCore.Qt.ItemIsSelectable)
            self.tree.addTopLevelItem(cat_item)

            for s in filtered:
                item = QtWidgets.QTreeWidgetItem([s["name"]])
                item.setData(0, QtCore.Qt.UserRole, s)
                cat_item.addChild(item)

            # РАСКРЫВАЕМ ВСЕГДА
            cat_item.setExpanded(True)

        # На всякий случай — раскроем всё
        self.tree.expandAll()

        # Если совсем пусто — добавим мягкую подсказку
        if total_nodes == 0:
            hint = QtWidgets.QTreeWidgetItem(["(нет доступных нод)"])
            hint.setFlags(hint.flags() & ~QtCore.Qt.ItemIsSelectable)
            self.tree.addTopLevelItem(hint)

    # ---------- действия ----------
    def _on_item_activated(self, item: QtWidgets.QTreeWidgetItem, _col: int):
        spec = item.data(0, QtCore.Qt.UserRole)
        if not spec:
            return  # клик по заголовку категории

        graph = self.main_window.get_active_graph()
        if not graph:
            return

        # Порядок попыток: по имени → по id → по type
        tried = []
        for token_key in ("by_name", "by_id", "type"):
            token = spec.get(token_key)
            if not token:
                continue
            try:
                node = graph.create_node(token)
                return  # успех
            except Exception as e:
                tried.append(f"{token_key}={token}: {e}")

        logger.warning("Не удалось создать ноду '%s'. Попытки: %s",
                       spec.get("name", "?"), " | ".join(tried))


def create_nodes_palette_dock(main_window) -> None:
    """
    Док с вкладками палитр:
      - Все
      - Высоты (идентификатор начинается с 'Ландшафт')
      - Климат   (идентификатор начинается с 'Климат')
      - Биомы    (идентификатор начинается с 'Биомы')
    Если у тебя другие префиксы — поправь тут один раз.
    """
    tabs = QtWidgets.QTabWidget()

    def make_tab(title: str, pred):
        w = NodesPaletteWidget(main_window, include_predicate=pred)
        tabs.addTab(w, title)

    # Все ноды
    make_tab("Все", lambda ident, name, node_id: True)
    # Высоты / климат / биомы по префиксам идентификатора категории
    make_tab("Высоты", lambda ident, *_: ident.startswith("Ландшафт"))
    make_tab("Климат", lambda ident, *_: ident.startswith("Климат"))
    make_tab("Биомы",  lambda ident, *_: ident.startswith("Биомы"))

    dock = QtWidgets.QDockWidget("Палитра Нодов", main_window)
    dock.setObjectName("Панель 'Палитра Нодов'")
    dock.setWidget(tabs)

    main_window.addDockWidget(QtCore.Qt.LeftDockWidgetArea, dock)
    main_window.dock_nodes = dock