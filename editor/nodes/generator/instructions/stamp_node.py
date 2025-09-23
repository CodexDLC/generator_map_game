# ==============================================================================
# Файл: editor/nodes/stamp_node.py
# Назначение: Нода-инструкция, описывающая параметры штампа.
# ==============================================================================
from editor.nodes.base_node import GeneratorNode


class StampNode(GeneratorNode):
    # Поместим ее в новую категорию "Инструкции"
    __identifier__ = 'Ландшафт.Инструкции'
    NODE_NAME = 'Stamp'

    def __init__(self):
        super().__init__()

        # У этой ноды нет входов, только выход с данными
        self.add_output('Stamp Data', 'Out')

        # Настраиваемые параметры самого штампа
        self.add_text_input('stamp_path', 'Stamp Path', text='path/to/stamp.png')
        self.add_text_input('stamp_amp', 'Amplitude (m)', text='150.0')
        self.add_text_input('stamp_scale', 'Scale (tiles)', text='2048')
        self.add_text_input('stamp_falloff', 'Falloff (0-1)', text='0.4')

        self.set_color(60, 60, 60)

    def compute(self, context):
        """
        Этот метод не вычисляет карту высот, а просто собирает все свои
        параметры в словарь и возвращает его.
        """

        def _f(name, default):
            v = self.get_property(name)
            try:
                return float(v)
            except (ValueError, TypeError):
                return default

        stamp_data = {
            "path": self.get_property('stamp_path'),
            "amp_m": _f('stamp_amp', 150.0),
            "scale_tiles": _f('stamp_scale', 2048.0),
            "falloff_range": _f('stamp_falloff', 0.4)
        }

        # Возвращаем не карту высот, а словарь с данными!
        self._result_cache = stamp_data
        return self._result_cache