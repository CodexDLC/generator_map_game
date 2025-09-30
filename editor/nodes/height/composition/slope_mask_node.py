# ==============================================================================
# Файл: editor/nodes/height/composition/slope_mask_node.py
# АРХИТЕКТУРА: "Творческая" [0..1]
# - Логика вынесена в generator_logic.masks.masking.create_slope_mask
# - Нода является UI-оберткой.
# ==============================================================================

from __future__ import annotations
from editor.nodes.base_node import GeneratorNode
from generator_logic.masks.masking import create_slope_mask

class SlopeMaskNode(GeneratorNode):
    """
    Категория: Ландшафт.Маски
    Роль: Маска по уклону (в градусах) из входной карты высот.

    Вход:
      0) Height In — карта высот (0..1)

    Выход:
      - Mask (0..1)

    Параметры:
      [Slope]
        - Min Angle (deg)   : нижняя граница диапазона
        - Max Angle (deg)   : верхняя граница диапазона
        - Edge Softness (°) : ширина плавного перехода (falloff) около границ
        - Invert            : инвертировать маску
    """

    __identifier__ = 'Ландшафт.Маски'
    NODE_NAME = 'Slope Mask'

    def __init__(self):
        super().__init__()

        self.add_input('Height In', 'In')
        self.add_output('Mask', 'Out')

        self.add_text_input('min_deg', 'Min Angle (deg)',   tab='Slope', text='10.0')
        self.add_text_input('max_deg', 'Max Angle (deg)',   tab='Slope', text='45.0')
        self.add_text_input('soft_deg', 'Edge Softness (°)', tab='Slope', text='4.0')
        self.add_checkbox('invert',    'Invert',            tab='Slope', state=False)

        self.set_color(80, 80, 30)
        self.set_description("""
        Строит маску по уклону поверхности.
        Угол θ берётся как arctan(|∇h|) в градусах. Диапазон [Min..Max] даёт 1.0,
        с плавными краями шириной ±Edge Softness. Можно инвертировать.
        """)

    def _get_float_param(self, name: str, default: float) -> float:
        try:
            return float(self.get_property(name))
        except (ValueError, TypeError):
            return default

    def compute(self, context: dict):
        height_in_port = self.get_input(0)
        
        # Получаем входную карту высот [0..1]
        if height_in_port and height_in_port.connected_ports():
            height_map_01 = height_in_port.connected_ports()[0].node().compute(context)
        else:
            height_map_01 = None # Бизнес-логика обработает это

        # Собираем параметры из UI
        min_angle = self._get_float_param('min_deg', 10.0)
        max_angle = self._get_float_param('max_deg', 45.0)
        softness = self._get_float_param('soft_deg', 4.0)
        invert = bool(self.get_property('invert'))

        # Вызываем бизнес-логику
        result_mask = create_slope_mask(
            context=context,
            height_map_01=height_map_01,
            min_angle_deg=min_angle,
            max_angle_deg=max_angle,
            edge_softness_deg=softness,
            invert=invert
        )

        self._result_cache = result_mask
        return self._result_cache
