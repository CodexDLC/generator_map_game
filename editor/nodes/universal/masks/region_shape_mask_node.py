# editor/nodes/universal/masks/region_shape_mask_node.py
from __future__ import annotations
import numpy as np

from editor.nodes.base_node import GeneratorNode
# Импортируем нашу новую бизнес-логику
from generator_logic.masks import shape_masks

class RegionShapeMaskNode(GeneratorNode):
    """
    Генерирует маску формы региона [0..1] (гексагон или круг)
    с плавным затуханием краев.
    """
    __identifier__ = "Универсальные.Маски" # Помещаем в категорию Маски
    NODE_NAME = "Region Shape Mask"

    def __init__(self):
        super().__init__()
        # Входы не нужны, так как координаты берутся из контекста
        self.add_output('Out') # Выходной порт для маски

        # Параметры в UI
        self.add_enum_input(
            "shape_type",
            "Shape",
            ["Hexagon", "Circle"], # Пока два варианта
            tab="Params",
            group="Shape",
            default="Hexagon" # По умолчанию гексагон
        )
        self.add_float_input(
            "fade_ratio",
            "Fade Ratio", # Переименовали для ясности
            value=0.15,
            tab="Params",
            group="Shape",
            p_range=(0.0, 1.0), # Диапазон от 0 до 1
            p_widget="slider"
        )
        # Добавим описание ноды
        self.set_description(
            "Создает маску [0..1], соответствующую форме региона.\n"
            "- Hexagon: Гексагональная маска с плавным затуханием от вписанной окружности к краям.\n"
            "- Circle: Круглая маска с плавным затуханием.\n"
            "Использует координаты и размер мира из глобального контекста."
        )
        # Зададим цвет ноды
        self.set_color(50, 90, 50) # Зеленоватый цвет для масок

    def _compute(self, context: dict) -> np.ndarray:
        """
        Вычисляет маску формы региона.
        """
        shape_type = self.get_property("shape_type")
        fade_ratio = self.get_property("fade_ratio")

        if shape_type == "Circle":
            # Вызываем функцию для круглой маски
            result_mask = shape_masks.generate_circular_mask(
                context,
                fade_width_pct=fade_ratio # Передаем fade_ratio как % ширины
            )
        else: # По умолчанию или если выбрано "Hexagon"
            # Вызываем функцию для гексагональной маски
            result_mask = shape_masks.generate_hexagonal_mask(
                context,
                fade_ratio=fade_ratio # Передаем fade_ratio напрямую
            )

        # Кэшируем и возвращаем результат
        self._result_cache = result_mask.astype(np.float32)
        return self._result_cache