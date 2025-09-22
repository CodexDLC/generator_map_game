# ==============================================================================
# Файл: editor/nodes/blend_node.py
# Назначение: Нода для смешивания двух карт высот по маске.
# ==============================================================================
import numpy as np
from editor.nodes.base_node import GeneratorNode
# Импортируем нашу новую функцию из движка
from game_engine_restructured.algorithms.terrain.steps.blending import blend_layers

class BlendNode(GeneratorNode):
    __identifier__ = 'generator.pipeline'
    NODE_NAME = 'Blend'

    def __init__(self):
        super().__init__()

        # --- Три входа, как мы и обсуждали ---
        self.add_input('A (Background)', 'A (BG)')
        self.add_input('B (Foreground)', 'B (FG)')
        self.add_input('Mask', 'Mask')

        # --- Один выход с результатом ---
        self.add_output('Out')

        # Задаем цвет для визуального отличия
        self.set_color(40, 40, 80)

    def compute(self, context):
        # A (BG) — порт 0
        port_a = self.get_input(0)
        layer_a = port_a.connected_ports()[0].node().compute(context) if (port_a and port_a.connected_ports()) \
            else np.zeros_like(context["x_coords"])

        # B (FG) — порт 1
        port_b = self.get_input(1)
        if not (port_b and port_b.connected_ports()):
            self._result_cache = layer_a
            return self._result_cache
        layer_b = port_b.connected_ports()[0].node().compute(context)

        # Mask — порт 2
        port_mask = self.get_input(2)
        if port_mask and port_mask.connected_ports():
            mask = port_mask.connected_ports()[0].node().compute(context)
            mmin, mmax = mask.min(), mask.max()
            mask = (mask - mmin) / (mmax - mmin + 1e-6)
        else:
            mask = np.ones_like(context["x_coords"])

        final_map = blend_layers(layer_a, layer_b, mask)
        self._result_cache = final_map
        return final_map
