# ==============================================================================
# Файл: editor/nodes/mask_node.py
# Назначение: Нода для создания черно-белой маски из входных данных.
# ==============================================================================
import numpy as np
from editor.nodes.base_node import GeneratorNode
# Импортируем нашу готовую функцию из движка
from game_engine_restructured.numerics.masking import create_mask

class MaskNode(GeneratorNode):
    # Поместим ее в категорию модулей, так как она создает данные для других нод
    __identifier__ = 'generator.modules'
    NODE_NAME = 'Mask'

    def __init__(self):
        super().__init__()

        # Вход для карты, которую будем превращать в маску
        self.add_input('Input', 'In')
        # Выход с готовой маской
        self.add_output('Mask', 'Out')

        # Добавляем настраиваемые параметры
        self.add_text_input('threshold', 'Threshold (0-1)', tab='Mask Settings', text='0.5')
        self.add_text_input('fade_range', 'Fade Range (0-1)', tab='Mask Settings', text='0.1')
        self.add_checkbox('invert', 'Invert', tab='Mask Settings', state=False)

        # Задаем цвет для визуального отличия
        self.set_color(80, 80, 25)

    def compute(self, context):
        # Получаем данные с входа
        input_port = self.get_input(0)
        if input_port and input_port.connected_ports():
            source_node = input_port.connected_ports()[0].node()
            input_map = source_node.compute(context)
        else:
            # Если ничего не подключено, возвращаем пустую (черную) маску
            self._result_cache = np.zeros_like(context["x_coords"])
            return self._result_cache

        # Получаем параметры из виджетов
        def _f(name, default):
            v = self.get_property(name)
            try: return float(v)
            except (ValueError, TypeError): return default

        threshold = _f('threshold', 0.5)
        fade_range = _f('fade_range', 0.1)
        invert = bool(self.get_property('invert'))

        # --- Нормализуем входные данные в диапазон [0, 1] ---
        # Это важно, чтобы порог (threshold) всегда работал одинаково,
        # независимо от того, какая карта высот пришла на вход.
        min_val, max_val = input_map.min(), input_map.max()
        if max_val - min_val > 1e-6:
            normalized_input = (input_map - min_val) / (max_val - min_val)
        else:
            normalized_input = np.zeros_like(input_map)

        # --- Вызываем "мозг" для создания маски ---
        print("  -> [MaskNode] Creating mask...")
        mask = create_mask(
            base_noise=normalized_input,
            threshold=threshold,
            invert=invert,
            fade_range=fade_range
        )

        self._result_cache = mask
        return self._result_cache