# ==============================================================================
# Файл: editor/nodes/base_node.py
# ВЕРСИЯ 2.1: Исправлено создание свойств согласно анализу.
# ==============================================================================

from NodeGraphQt import BaseNode

class GeneratorNode(BaseNode):
    __identifier__ = 'generator.nodes'

    def __init__(self):
        super().__init__()
        self._result_cache = None

        # НЕ вызываем create_property('node_id', ...)
        # 1) создаём виджет -> он сам создаст property 'node_id'
        self.add_text_input('node_id', 'Node ID', tab='Node')

        # 2) выставляем значение
        self.set_property('node_id', self.id)

        # 3) делаем read-only (если метод доступен в твоей сборке)
        w = self.get_widget('node_id')
        if w:
            try:
                w.set_read_only(True)
            except AttributeError:
                pass