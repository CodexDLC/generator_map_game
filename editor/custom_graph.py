# ==============================================================================
# Файл: editor/custom_graph.py
# Назначение: Кастомный класс графа с переопределенным контекстным меню
#             для создания нод.
# ВЕРСИЯ 1.0
# ==============================================================================
from PySide6 import QtWidgets
from NodeGraphQt import NodeGraph
from collections import defaultdict


class CustomNodeGraph(NodeGraph):
    """
    Наследуемся от NodeGraph, чтобы переопределить стандартное контекстное меню
    и создать свое, с категориями.
    """

    def __init__(self, parent=None):
        super(CustomNodeGraph, self).__init__(parent)

    def _on_show_context_menu(self, pos):
        """
        Вызывается при клике правой кнопкой мыши.
        Полностью заменяет стандартное меню на наше.
        """
        # --- 1. Собираем и группируем все зарегистрированные ноды ---

        # Создаем словарь, где ключи - это пути категорий (например, "Ландшафт.Пайплайн"),
        # а значения - списки нод в этой категории.
        nodes_by_category = defaultdict(list)
        for node_id, node_class in self.registered_nodes().items():
            # Пропускаем стандартные ноды, которые мы не хотим видеть в меню
            if 'nodeGraphQt' in node_id or 'nodes.Backdrop' in node_id:
                continue

            # Идентификатор нашей ноды (например, 'Ландшафт.Эффекты')
            category_path = node_class.__identifier__
            nodes_by_category[category_path].append(node_class)

        # --- 2. Строим меню на основе сгруппированных нод ---

        menu = QtWidgets.QMenu(self.widget)

        selected = self.selected_nodes()
        if selected:
            act_del = menu.addAction("Удалить выбранные")
            act_del.triggered.connect(lambda: self.delete_nodes(self.selected_nodes()))
            menu.addSeparator()

        # Рекурсивная функция для создания вложенных меню
        def build_menu(parent_menu, path_dict):
            sub_menus = defaultdict(dict)
            actions = []

            for path, nodes in path_dict.items():
                parts = path.split('.', 1)
                current_level_name = parts[0]

                if len(parts) > 1:
                    # Это вложенная категория, добавляем ее в sub_menus
                    sub_menus[current_level_name][parts[1]] = nodes
                else:
                    # Это конечная категория, добавляем ноды как действия
                    for node in sorted(nodes, key=lambda n: n.NODE_NAME):
                        action = parent_menu.addAction(node.NODE_NAME)
                        action.triggered.connect(lambda checked=False, n=node: self.create_node(n.NODE_NAME, pos=pos))
                        actions.append(action)

            # Сначала добавляем подменю (отсортированные по имени)
            for menu_name in sorted(sub_menus.keys()):
                sub_menu = parent_menu.addMenu(menu_name)
                build_menu(sub_menu, sub_menus[menu_name])

            # Затем добавляем действия (ноды) в текущем меню
            if actions:
                if sub_menus:  # Если есть и подменю и ноды, добавляем разделитель
                    parent_menu.addSeparator()
                for action in actions:
                    parent_menu.addAction(action)

        build_menu(menu, nodes_by_category)

        menu.exec_(self.widget.mapToGlobal(pos))