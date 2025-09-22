# ==============================================================================
# Файл: editor/nodes/generator/effects/slope_limiter_node.py
# Назначение: Нода для итеративного ограничения максимального уклона.
# ==============================================================================
import numpy as np
import math
from editor.nodes.base_node import GeneratorNode
# Импортируем "мозг" из нашего движка
from game_engine_restructured.numerics.slope import apply_slope_limiter


class SlopeLimiterNode(GeneratorNode):
    __identifier__ = 'generator.effects'
    NODE_NAME = 'Slope Limiter'

    def __init__(self):
        super().__init__()

        # --- Входы и выходы ---
        self.add_input('In')
        self.add_output('Out')

        # --- Настройки ---
        self.add_text_input('max_angle_deg', 'Max Slope Angle (°)', '45.0', tab='Settings')
        self.add_text_input('iterations', 'Iterations', '4', tab='Settings')

        self.set_color(90, 80, 30)  # Финальный оттенок оранжевого в этой категории

    def compute(self, context):
        port_in = self.get_input(0)
        if not (port_in and port_in.connected_ports()):
            return context["main_heightmap"]

        height_map = port_in.connected_ports()[0].node().compute(context).copy()

        def _f(name, default):
            v = self.get_property(name)
            try:
                return float(v)
            except (ValueError, TypeError):
                return default

        def _i(name, default):
            v = self.get_property(name)
            try:
                return int(v)
            except (ValueError, TypeError):
                return default

        max_angle = _f('max_angle_deg', 45.0)
        iterations = _i('iterations', 4)

        # Функция в движке ожидает тангенс угла, а пользователю удобнее вводить градусы.
        # Конвертируем градусы в тангенс прямо здесь.
        max_slope_tangent = math.tan(math.radians(max_angle))

        cell_size = context.get("cell_size", 1.0)

        # Вызываем "мозг" из движка.
        # Важно: эта функция модифицирует массив "на месте", поэтому мы передаем копию.
        result_map = apply_slope_limiter(height_map, max_slope_tangent, cell_size, iterations)

        self._result_cache = result_map
        return self._result_cache