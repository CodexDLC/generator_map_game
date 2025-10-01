# editor/nodes/height/erosion/landlab_erosion_node.py
import numpy as np
from editor.nodes.base_node import GeneratorNode
from generator_logic.terrain.landlab_erosion import landlab_erosion_wrapper

class LandlabErosionNode(GeneratorNode):
    __identifier__ = "Высоты.Эрозия"
    NODE_NAME = "Erosion (Landlab)"

    def __init__(self):
        super().__init__()
        # входная карта высот
        self.add_input("In", display_name=False)
        # выход
        self.add_output("Out")
        # параметры: dt, K_sp, m_sp, n_sp, diffusivity, num_steps
        self.add_float_input("dt", "Δt (год)", value=1.0, tab="Params", group="Erosion",
                             p_range=(0.01, 10.0), p_widget='slider')
        self.add_float_input("K_sp", "K (эродимость)", value=5e-6, tab="Params", group="Erosion",
                             p_range=(1e-7, 1e-4), p_widget='slider')
        self.add_float_input("m_sp", "m (stream-power)", value=0.5, tab="Params", group="Erosion",
                             p_range=(0.0, 1.0), p_widget='slider')
        self.add_float_input("n_sp", "n (stream-power)", value=1.0, tab="Params", group="Erosion",
                             p_range=(0.5, 2.0), p_widget='slider')
        self.add_float_input("diffusivity", "Diffusivity", value=0.01, tab="Params", group="Erosion",
                             p_range=(0.0, 0.1), p_widget='slider')
        self.add_float_input("num_steps", "Steps", value=1, tab="Params", group="Erosion",
                             p_range=(1, 10), p_widget='spinbox')
        self.set_color(90, 40, 40)  # тёмно-красная нода для «эрозии»

    def _compute(self, context):
        # берём входную карту (например, высота)
        inputs = self.inputs()
        if "In" not in inputs or not inputs["In"].connected_ports():
            return None  # если нет входа — ничего делать
        # вычисляем входную карту (вызов compute у подключённой ноды)
        in_port = inputs["In"].connected_ports()[0]
        height_map = in_port.node().compute(context)
        if height_map is None:
            return None

        # собираем параметры из UI
        params = {
            "dt": float(self.get_property("dt")),
            "K_sp": float(self.get_property("K_sp")),
            "m_sp": float(self.get_property("m_sp")),
            "n_sp": float(self.get_property("n_sp")),
            "diffusivity": float(self.get_property("diffusivity")),
            "num_steps": int(float(self.get_property("num_steps"))),
        }

        try:
            result = landlab_erosion_wrapper(context, height_map, params)
        except ImportError:
            # Если Landlab не установлен, можно вернуть исходную карту без изменений
            result = height_map.astype(np.float32)
        self._result_cache = result
        return result
