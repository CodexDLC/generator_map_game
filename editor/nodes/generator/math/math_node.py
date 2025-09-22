# ==============================================================================
# Файл: editor/nodes/generator/math/math_node.py
# Назначение: Нода для выполнения математических операций.
# ==============================================================================
import numpy as np
from editor.nodes.base_node import GeneratorNode


class MathNode(GeneratorNode):
    # Указываем новую категорию для палитры нодов
    __identifier__ = 'generator.math'
    NODE_NAME = 'Math'

    def __init__(self):
        super().__init__()

        # --- Входы и выходы ---
        self.add_input('A', 'In')
        self.add_input('B', 'In')  # Второй вход, может быть картой или числом
        self.add_output('Out')

        # --- Настройки в панели свойств ---
        self.add_combo_menu('operation', 'Operation',
                            items=['Add', 'Subtract', 'Multiply', 'Power'],
                            tab='Settings')
        self.add_text_input('const_b', 'Constant B', '0.0', tab='Settings')

        self.set_color(40, 60, 90) # Синеватый цвет для математики

    def compute(self, context):
        # --- Получаем данные с входа A (обязательный) ---
        port_a = self.get_input(0)
        if not (port_a and port_a.connected_ports()):
            # Если на главный вход ничего не подано, возвращаем нули
            return np.zeros_like(context["x_coords"])
        layer_a = port_a.connected_ports()[0].node().compute(context)

        # --- Получаем данные для B (карта ИЛИ константа) ---
        port_b = self.get_input(1)
        if port_b and port_b.connected_ports():
            # Если ко входу B что-то подключено, используем эту карту
            layer_b = port_b.connected_ports()[0].node().compute(context)
        else:
            # Иначе, берем значение из числового поля
            try:
                layer_b = float(self.get_property('const_b'))
            except (ValueError, TypeError):
                layer_b = 0.0

        # --- Выполняем операцию ---
        op = self.get_property('operation')

        if op == 'Add':
            result = layer_a + layer_b
        elif op == 'Subtract':
            result = layer_a - layer_b
        elif op == 'Multiply':
            result = layer_a * layer_b
        elif op == 'Power':
            result = np.power(layer_a, layer_b)
        else:
            result = layer_a # По умолчанию ничего не делаем

        self._result_cache = result.astype(np.float32)
        return self._result_cache


class MathNode(GeneratorNode):
    # Указываем новую категорию для палитры нодов
    __identifier__ = 'generator.math'
    NODE_NAME = 'Math'

    def __init__(self):
        super().__init__()

        # --- Входы и выходы ---
        self.add_input('A', 'In')
        self.add_input('B', 'In')  # Второй вход, может быть картой или числом
        self.add_output('Out')

        # --- Настройки в панели свойств ---
        self.add_combo_menu('operation', 'Operation',
                            items=['Add', 'Subtract', 'Multiply', 'Power'],
                            tab='Settings')
        self.add_text_input('const_b', 'Constant B', '0.0', tab='Settings')

        self.set_color(40, 60, 90)  # Синеватый цвет для математики

    def compute(self, context):
        # --- Получаем данные с входа A (обязательный) ---
        port_a = self.get_input(0)
        if not (port_a and port_a.connected_ports()):
            # Если на главный вход ничего не подано, возвращаем нули
            return np.zeros_like(context["x_coords"])
        layer_a = port_a.connected_ports()[0].node().compute(context)

        # --- Получаем данные для B (карта ИЛИ константа) ---
        port_b = self.get_input(1)
        if port_b and port_b.connected_ports():
            # Если ко входу B что-то подключено, используем эту карту
            layer_b = port_b.connected_ports()[0].node().compute(context)
        else:
            # Иначе, берем значение из числового поля
            try:
                layer_b = float(self.get_property('const_b'))
            except (ValueError, TypeError):
                layer_b = 0.0

        # --- Выполняем операцию ---
        op = self.get_property('operation')

        if op == 'Add':
            result = layer_a + layer_b
        elif op == 'Subtract':
            result = layer_a - layer_b
        elif op == 'Multiply':
            result = layer_a * layer_b
        elif op == 'Power':
            result = np.power(layer_a, layer_b)
        else:
            result = layer_a  # По умолчанию ничего не делаем

        self._result_cache = result.astype(np.float32)
        return self._result_cache


class ClampNode(GeneratorNode):
    __identifier__ = 'generator.math'
    NODE_NAME = 'Clamp'

    def __init__(self):
        super().__init__()
        self.add_input('In')
        self.add_output('Out')

        self.add_text_input('min_val', 'Min', '-1000.0', tab='Settings')
        self.add_text_input('max_val', 'Max', '1000.0', tab='Settings')

        self.set_color(40, 70, 90)

    def compute(self, context):
        port_in = self.get_input(0)
        if not (port_in and port_in.connected_ports()):
            return np.zeros_like(context["x_coords"])
        layer_in = port_in.connected_ports()[0].node().compute(context)

        try:
            min_v = float(self.get_property('min_val'))
        except (ValueError, TypeError):
            min_v = -1000.0
        try:
            max_v = float(self.get_property('max_val'))
        except (ValueError, TypeError):
            max_v = 1000.0

        result = np.clip(layer_in, min_v, max_v)

        self._result_cache = result.astype(np.float32)
        return self._result_cache


class NormalizeNode(GeneratorNode):
    __identifier__ = 'generator.math'
    NODE_NAME = 'Normalize'

    def __init__(self):
        super().__init__()
        self.add_input('In')
        self.add_output('Out')
        self.set_color(40, 80, 90)

    def compute(self, context):
        port_in = self.get_input(0)
        if not (port_in and port_in.connected_ports()):
            return np.zeros_like(context["x_coords"])
        layer_in = port_in.connected_ports()[0].node().compute(context)

        min_val = layer_in.min()
        max_val = layer_in.max()

        range_val = max_val - min_val
        if range_val > 1e-6:
            result = (layer_in - min_val) / range_val
        else:
            result = np.zeros_like(layer_in)

        self._result_cache = result.astype(np.float32)
        return self._result_cache