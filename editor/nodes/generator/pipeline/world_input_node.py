# ==============================================================================
# Файл: editor/nodes/world_input_node.py
# ВЕРСИЯ 4.0: Убран вход для варпинга для максимального упрощения.
#             Нода теперь является чистым источником глобального шума.
# ==============================================================================
import logging
import numpy as np
from editor.nodes.base_node import GeneratorNode
from game_engine_restructured.algorithms.terrain.steps.noise import _generate_noise_field

logger = logging.getLogger(__name__)

class WorldInputNode(GeneratorNode):
    __identifier__ = 'generator.pipeline'
    NODE_NAME = 'World Input'

    def __init__(self):
        super().__init__()

        self.add_output('height')
        self.set_color(80, 25, 30)

    def compute(self, context):
        """
        Генерирует "сырой" ландшафт, используя глобальные параметры из контекста.
        """
        node_id = self.get_property('node_id')
        logger.info(f"Computing WorldInputNode (ID: {node_id})...")

        noise_params = context.get("global_noise")
        if not isinstance(noise_params, dict):
            logger.critical(f"Node {node_id}: 'global_noise' parameters not found in context! Returning zeros.")
            return np.zeros_like(context["x_coords"])

        logger.debug(f"  - Using global_noise params: {noise_params}")

        # Добавляем служебные параметры
        params_for_generation = noise_params.copy()
        params_for_generation["seed_offset"] = 0
        params_for_generation["blend_mode"] = "replace"

        # Вызываем генератор с глобальными параметрами и оригинальным контекстом
        height_map = _generate_noise_field(params_for_generation, context)

        # Мониторинг данных (Sanity Check)
        if height_map is not None:
            logger.debug(f"  - Output map stats: shape={height_map.shape}, "
                         f"min={height_map.min():.2f}, max={height_map.max():.2f}, "
                         f"has_nan={np.isnan(height_map).any()}")
        else:
            # Эта ситуация не должна происходить, но логируем на всякий случай
            logger.error(f"  - _generate_noise_field returned None!")

        self._result_cache = height_map
        return self._result_cache