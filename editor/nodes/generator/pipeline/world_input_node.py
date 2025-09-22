# ==============================================================================
# Файл: editor/nodes/world_input_node.py
# ВЕРСИЯ 4.0: Убран вход для варпинга для максимального упрощения.
#             Нода теперь является чистым источником глобального шума.
# ==============================================================================
import numpy as np
from editor.nodes.base_node import GeneratorNode
from game_engine_restructured.algorithms.terrain.steps.noise import _generate_noise_field


class WorldInputNode(GeneratorNode):
    __identifier__ = 'generator.pipeline'
    NODE_NAME = 'World Input'

    def __init__(self):
        super().__init__()

        # --- УДАЛЕН ВХОД 'warp_field' ---
        # self.add_input('warp_field', 'Warp Field (optional)')
        self.add_output('height')

        # Настройки из UI больше не нужны
        self.set_color(80, 25, 30)

    def compute(self, context):
        """
        Генерирует "сырой" ландшафт, используя глобальные параметры из контекста.
        """
        # --- УДАЛЕНА ВСЯ ЛОГИКА ВАРПИНГА ---
        # Код, который проверял warp_port и менял координаты, убран.

        # Получаем параметры из контекста, как и раньше
        noise_params = context.get("global_noise")
        if not isinstance(noise_params, dict):
            print("!!! [WorldInput] CRITICAL ERROR: Параметры 'global_noise' не найдены в контексте!")
            return np.zeros_like(context["x_coords"])

        # Добавляем служебные параметры
        noise_params["seed_offset"] = 0
        noise_params["blend_mode"] = "replace"

        # Вызываем генератор с глобальными параметрами и оригинальным контекстом
        height_map = _generate_noise_field(noise_params, context)

        self._result_cache = height_map
        return self._result_cache