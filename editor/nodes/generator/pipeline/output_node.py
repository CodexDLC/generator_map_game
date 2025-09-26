# editor/nodes/output_node.py
from editor.nodes.base_node import GeneratorNode
import logging

logger = logging.getLogger(__name__)

class OutputNode(GeneratorNode):
    __identifier__ = 'Ландшафт.Пайплайн'
    NODE_NAME = 'Output'

    def __init__(self):
        super(OutputNode, self).__init__()
        self.add_input('in', color=(180, 80, 0))
        self.set_color(10, 20, 30)
        self.set_description("""
        Финальная нода пайплайна. Получает результат с единственного входа
        и инициирует вычисление графа, кэшируя финальный результат.
        Если вход не подключен — поднимает RuntimeError.
        """)

    def compute(self, *args, **kwargs):
        input_port = self.get_input(0)
        if not input_port or not input_port.connected_ports():
            raise RuntimeError("Вход ноды 'Output' не подключен!")
        source_node = input_port.connected_ports()[0].node()
        logger.debug("--- Computing final result from: %s ---", source_node.name())
        result = source_node.compute(*args, **kwargs)
        self._result_cache = result
        return self._result_cache
