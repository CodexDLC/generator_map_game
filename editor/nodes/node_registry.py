# ==============================================================================
# Файл: editor/nodes/node_registry.py
# Назначение: Единая точка для регистрации всех нодов в приложении.
# ==============================================================================

# Импортируем все наши классы нодов
from .world_input_node import WorldInputNode
from .noise_node import NoiseNode
from .output_node import OutputNode


def register_all_nodes(graph):
    """
    Регистрирует все доступные ноды в переданном графе.

    Args:
        graph (NodeGraphQt.NodeGraph): Экземпляр графа, в котором нужно
                                       зарегистрировать ноды.
    """
    print("[NodeRegistry] Registering all nodes...")

    # Просто добавляйте сюда новые ноды по мере их создания
    graph.register_node(WorldInputNode)
    graph.register_node(NoiseNode)
    graph.register_node(OutputNode)

    print("[NodeRegistry] All nodes registered.")