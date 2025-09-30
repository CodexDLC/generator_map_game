# editor/graph_utils.py
from NodeGraphQt import NodeGraph
from .nodes.node_registry import register_all_nodes

def create_default_graph_session() -> dict:
    """
    Создает временный граф и возвращает его сериализованные данные.
    """
    temp_graph = NodeGraph()
    register_all_nodes(temp_graph)
    return temp_graph.serialize_session()