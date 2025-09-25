# editor/graph/queries.py
from PySide6 import QtWidgets

def find_output_node(graph):
    if not graph:
        return None
    try:
        nodes = list(graph.all_nodes())
    except Exception:
        return None
    outs = [n for n in nodes if getattr(n, "NODE_NAME", "") == "Output"]
    return outs[0] if outs else None

def require_output_node(parent, graph):
    node = find_output_node(graph)
    if not node:
        QtWidgets.QMessageBox.warning(parent, "Ошибка графа", "В графе отсутствует нода 'Output'.")
        return None
    return node
