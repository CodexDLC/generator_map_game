# editor/graph_utils.py
from NodeGraphQt import NodeGraph
from .nodes.node_registry import register_all_nodes

def create_default_graph_session() -> dict:
    """
    Создает временный граф, добавляет ноды по умолчанию, соединяет их
    и возвращает сериализованные данные. Это гарантирует правильный формат.
    """
    temp_graph = NodeGraph()
    register_all_nodes(temp_graph)

    input_node = temp_graph.create_node('Ландшафт.Пайплайн.WorldInputNode', name='Вход', pos=(-300, 0))
    output_node = temp_graph.create_node('Ландшафт.Пайплайн.OutputNode', name='Выход', pos=(100, 0))

    input_node.set_output(0, output_node.input(0))
    return temp_graph.serialize_session()