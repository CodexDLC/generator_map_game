# editor/nodes/universal/debug/sphere_projection_node.py
import numpy as np
from editor.nodes.base_node import GeneratorNode


class SphereProjectionNode(GeneratorNode):
    """
    Диагностическая нода для визуализации проекции на сферу.
    """
    __identifier__ = "Универсальные.Отладка"
    NODE_NAME = "Sphere Projection Viz"

    def __init__(self):
        super().__init__()
        self.add_output('Out')
        self.add_float_input("radius_km", "Радиус (км)", value=50.0, tab="Params", p_range=(1.0, 10000.0))

        self.set_color(120, 120, 40)  # Зададим ей заметный желто-зеленый цвет
        self.set_description(
            "Визуализирует проекцию на сферу. \n"
            "Выводит 'купол' полусферы в диапазоне [0, 1]. \n"
            "Используйте эту ноду, чтобы настроить радиус и увидеть, \n"
            "как кривизна мира будет влиять на глобальный ландшафт."
        )

    def _compute(self, context):
        x_coords_m = context['x_coords']
        z_coords_m = context['z_coords']

        radius_m = self.get_property('radius_km') * 1000.0
        if radius_m < 1.0:
            radius_m = 1.0

        # Нормализуем координаты относительно радиуса
        nx = x_coords_m / radius_m
        nz = z_coords_m / radius_m

        # Вычисляем Y-координату на единичной сфере
        d_sq = nx ** 2 + nz ** 2
        ny = np.sqrt(np.maximum(0.0, 1.0 - d_sq))

        # 'ny' — это и есть наш купол от 0 (на краях) до 1 (в центре).
        # Это идеальная визуализация кривизны.
        self._result_cache = ny.astype(np.float32)
        return self._result_cache