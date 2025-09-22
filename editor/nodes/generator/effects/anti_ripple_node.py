# ==============================================================================
# Файл: editor/nodes/generator/effects/anti_ripple_node.py
# Назначение: Нода для подавления среднечастотной "ряби" на ландшафте.
# ==============================================================================
from editor.nodes.base_node import GeneratorNode
# Импортируем "мозг" из нашего движка
from game_engine_restructured.numerics.new_test import anti_ripple


class AntiRippleNode(GeneratorNode):
    __identifier__ = 'generator.effects'
    NODE_NAME = 'Anti Ripple'

    def __init__(self):
        super().__init__()

        # --- Входы и выходы ---
        self.add_input('In')
        self.add_output('Out')

        # --- Настройки ---
        self.add_text_input('sigma_low', 'Low Freq Sigma', '9.0', tab='Filter')
        self.add_text_input('sigma_high', 'High Freq Sigma', '3.5', tab='Filter')
        self.add_text_input('alpha', 'Strength (Alpha)', '0.6', tab='Filter')

        self.add_text_input('slope_deg_mid', 'Slope Mid (°)', '22.0', tab='Slope Gate')
        self.add_text_input('slope_deg_hard', 'Slope Hard (°)', '38.0', tab='Slope Gate')

        self.set_color(80, 80, 40)  # Зеленовато-желтый цвет

    def compute(self, context):
        port_in = self.get_input(0)
        if not (port_in and port_in.connected_ports()):
            return context["main_heightmap"]

        height_map = port_in.connected_ports()[0].node().compute(context)

        def _f(name, default):
            v = self.get_property(name)
            try:
                return float(v)
            except (ValueError, TypeError):
                return default

        # Вызываем "мозг" из движка, передавая все параметры
        result_map = anti_ripple(
            height=height_map,
            cell_size=context.get("cell_size", 1.0),
            sigma_low=_f('sigma_low', 9.0),
            sigma_high=_f('sigma_high', 3.5),
            alpha=_f('alpha', 0.6),
            slope_deg_mid=_f('slope_deg_mid', 22.0),
            slope_deg_hard=_f('slope_deg_hard', 38.0)
        )

        self._result_cache = result_map
        return self._result_cache