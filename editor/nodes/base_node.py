# editor/nodes/base_node.py
from NodeGraphQt import BaseNode

class GeneratorNode(BaseNode):
    __identifier__ = 'generator.nodes'

    def __init__(self):
        super().__init__()
        self._result_cache = None
        self._is_dirty = True  # Нода "грязная" при создании

        self.add_text_input('node_name', 'Name', tab='Node Properties')
        self.add_text_input('node_id',   'Node ID', tab='Node Properties')
        self.set_property('node_name', self.name())
        self.set_property('node_id',   self.id)
        w = self.get_widget('node_id')
        if w and hasattr(w, 'set_tooltip'):
            w.set_tooltip('Read-only: managed by the node')

    def mark_dirty(self):
        """Помечает ноду и все последующие как 'грязные'."""
        if self._is_dirty:
            return  # Уже помечена, ничего не делаем

        self._is_dirty = True
        self._result_cache = None  # Сбрасываем кэш

        # Рекурсивно помечаем все ноды, которые зависят от этой
        for port in self.output_ports():
            for connected_port in port.connected_ports():
                node = connected_port.node()
                if isinstance(node, GeneratorNode):
                    node.mark_dirty()


    def set_property(self, name, value, push_undo=False, **kwargs):

        if self.get_property(name) != value:
            self.mark_dirty()

        if name == 'node_id':
            real_id = self.id
            if value != real_id:
                return super().set_property(name, real_id, push_undo=push_undo, **kwargs)
            return super().set_property(name, value, push_undo=push_undo, **kwargs)

        if name == 'node_name':
            if self.name() != str(value):
                self.set_name(str(value))

        return super().set_property(name, value, push_undo=push_undo, **kwargs)

    def compute(self, context):
        """
        "Умный" метод вычисления с кэшированием.
        Вызывает реальный пересчет только если нода "грязная".
        """
        if self._is_dirty:

            self._result_cache = self._compute(context)
            self._is_dirty = False  # Теперь нода "чистая"

        return self._result_cache

    def _compute(self, context):
        """
        Метод, который ДОЛЖЕН БЫТЬ переопределен в дочерних нодах.
        Здесь содержится реальная логика генерации.
        """
        raise NotImplementedError(
            f"Метод '_compute' не реализован в ноде '{self.name()}' (Тип: {self.__class__.__name__})"
        )
