# editor/graph/queries.py
from PySide6 import QtWidgets

# --- ДОБАВЛЯЕМ ИМПОРТ ВАШЕЙ НОДЫ ---
from ..nodes.height.io.output_node import OutputNode


# ------------------------------------

def find_output_node(graph):
    """Ищет финальную ноду в графе по её классу, а не по имени."""
    if not graph:
        return None
    try:
        nodes = list(graph.all_nodes())
    except Exception:
        return None

    # --- ИЗМЕНЯЕМ ПРОВЕРКУ ---
    # Было: ищем по имени "Output"
    # Стало: ищем по классу OutputNode
    outs = [n for n in nodes if isinstance(n, OutputNode)]
    # -------------------------

    return outs[0] if outs else None


def require_output_node(parent, graph):
    """Проверяет наличие выходной ноды и показывает ошибку, если её нет."""
    node = find_output_node(graph)
    if not node:
        # Теперь сообщение об ошибке будет более общим, но корректным
        QtWidgets.QMessageBox.warning(parent, "Ошибка графа",
                                      "В графе отсутствует обязательная выходная нода (OutputNode).")
        return None
    return node