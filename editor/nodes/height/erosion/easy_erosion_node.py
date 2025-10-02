# editor/nodes/height/erosion/easy_erosion_node.py
from __future__ import annotations
import numpy as np
from editor.nodes.base_node import GeneratorNode
from generator_logic.terrain.easy_erosion import easy_erosion_wrapper

class EasyErosionNode(GeneratorNode):
    """
    Нода «EasyErosion» — простой метод приглаживания, имитирующий осыпание песком.
    """
    __identifier__ = "Ландшафт.Эрозия"
    NODE_NAME = "EasyErosion"

    def __init__(self):
        super().__init__()
        # Вход и выход
        self.add_input("In", display_name=False)
        self.add_output("Out")

        # Сила эффекта (0..1)
        self.add_float_input(
            "influence",
            "Influence",
            value=0.5,
            tab="Params",
            group="EasyErosion",
            p_range=(0.0, 1.0),
            p_widget="slider",
        )
        # Размер ядра размытия (3..101 пикселей). Значение округлим до нечётного.
        self.add_float_input(
            "kernel_size",
            "Kernel Size",
            value=11.0,
            tab="Params",
            group="EasyErosion",
            p_range=(3.0, 101.0),
            p_widget="spinbox",
        )
        # Количество итераций размытия (1..10)
        self.add_float_input(
            "iterations",
            "Iterations",
            value=1.0,
            tab="Params",
            group="EasyErosion",
            p_range=(1.0, 10.0),
            p_widget="spinbox",
        )

        # Цвет ноды в графе
        self.set_color(120, 60, 30)

    def _compute(self, context: dict) -> np.ndarray | None:
        inputs = self.inputs()
        if not inputs["In"].connected_ports():
            return None

        # получаем карту высот от предыдущей ноды
        in_port = inputs["In"].connected_ports()[0]
        height_map = in_port.node().compute(context)
        if height_map is None:
            return None

        # собираем параметры из UI; приводим к числам
        params = {
            "influence": float(self.get_property("influence")),
            "kernel_size": int(float(self.get_property("kernel_size"))),
            "iterations": int(float(self.get_property("iterations"))),
        }

        # вызываем бизнес-логику
        result = easy_erosion_wrapper(context, height_map, params)
        # кешируем результат
        self._result_cache = result
        return result
