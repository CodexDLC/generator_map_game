# ==============================================================================
# Файл: editor/steps/output_node.py
# ВЕРСИЯ 2.1: Исправлен идентификатор для группировки.
# ==============================================================================

from editor.nodes.base_node import GeneratorNode


class OutputNode(GeneratorNode):
    # ИСПРАВЛЕНИЕ (п.8): Используем общий идентификатор.
    __identifier__ = 'Ландшафт.Пайплайн'
    NODE_NAME = 'Output'

    def __init__(self):
        super(OutputNode, self).__init__()
        self.add_input('in', color=(180, 80, 0))
        self.set_color(10, 20, 30)

    def compute(self, *args, **kwargs):
        input_port = self.get_input(0)
        if not input_port or not input_port.connected_ports():
            # ИЗМЕНЕНИЕ: Вызываем исключение вместо возврата None
            raise RuntimeError("Вход ноды 'Output' не подключен!")

        source_node = input_port.connected_ports()[0].node()

        print(f"--- Computing final result from: {source_node.name()} ---")
        result = source_node.compute(*args, **kwargs)
        self._result_cache = result
        return self._result_cache