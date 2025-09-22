# editor/nodes/base_node.py
from NodeGraphQt import BaseNode

class GeneratorNode(BaseNode):
    __identifier__ = 'generator.nodes'

    def __init__(self):
        super().__init__()
        self._result_cache = None

        # 1) свойства (виджеты сами создают property)
        self.add_text_input('node_name', 'Name', tab='Node Properties')
        self.add_text_input('node_id',   'Node ID', tab='Node Properties')

        # 2) значения по умолчанию
        self.set_property('node_name', self.name())
        self.set_property('node_id',   self.id)

        # 3) чисто косметика: подсказка, что поле read-only
        w = self.get_widget('node_id')
        if w and hasattr(w, 'set_tooltip'):
            w.set_tooltip('Read-only: managed by the node')

    # ВАЖНО: совместимая сигнатура (NodeGraphQt может звать push_undo и прочие kwargs)
    def set_property(self, name, value, push_undo=False, **kwargs):
        # защита от правки node_id из инспектора/сигналов фреймворка
        if name == 'node_id':
            # всегда держим id истинным; жёстко возвращаем
            real_id = self.id
            if value != real_id:
                # вернём корректное значение вверх по стеку
                return super().set_property(name, real_id, push_undo=push_undo, **kwargs)
            # если совпало — просто пропускаем дальше
            return super().set_property(name, value, push_undo=push_undo, **kwargs)

        # синхронизация заголовка с именем
        if name == 'node_name':
            if self.name() != str(value):
                self.set_name(str(value))

        return super().set_property(name, value, push_undo=push_undo, **kwargs)
