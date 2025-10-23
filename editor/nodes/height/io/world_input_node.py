# ==============================================================================
# Файл: editor/nodes/height/io/world_input_node.py
# ВЕРСИЯ 7.0: Упрощена. Теперь выдает только карту высот (3D-шум).
# Маска формы региона генерируется отдельной нодой RegionShapeMaskNode.
# ==============================================================================

import logging
import numpy as np
from editor.nodes.base_node import GeneratorNode
# Убираем импорт Port, так как compute_outputs удален
# from NodeGraphQt import Port

logger = logging.getLogger(__name__)

IDENTIFIER_LBL = "Ландшафт.Пайплайн"
NODE_NAME_LBL  = "World Input"
# Обновляем описание
DESCRIPTION_TEXT = """
Точка входа для графа. Предоставляет базовый ландшафт (3D-шум) [0..1],
сгенерированный на основе глобальных настроек мира и координат региона.
Маска формы региона (гексагон/круг) генерируется нодой 'Region Shape Mask'.
"""

class WorldInputNode(GeneratorNode):
    __identifier__ = IDENTIFIER_LBL
    NODE_NAME = NODE_NAME_LBL

    def __init__(self):
        super().__init__()
        # Оставляем только один выход
        self.add_output("height")
        # --- УДАЛЕНО: self.add_output("mask") ---
        self.set_color(80, 25, 30)
        self.set_description(DESCRIPTION_TEXT)

        # Оставляем только кэш для высоты
        self._result_cache_height: np.ndarray | None = None
        # --- УДАЛЕНО: self._result_cache_mask ---
        self._last_context_signature_computed = None

    # --- Упрощенный _compute ---
    def _compute(self, context):
        current_context_signature = id(context)

        # Пересчитываем только если нужно
        if self._is_dirty or self._last_context_signature_computed != current_context_signature:
            logger.debug(f"WorldInputNode ({self.name()}): Recalculating height...")
            # Получаем только высоту из контекста
            height_data = context.get("world_input_height", np.zeros_like(context["x_coords"]))

            # --- УДАЛЕНО: Получение mask_data ---

            # Кэшируем только высоту
            self._result_cache_height = height_data.copy()

            # --- УДАЛЕНО: Кэширование mask_data ---

            self._last_context_signature_computed = current_context_signature
            self._is_dirty = False # Сбрасываем флаг
            logger.debug(f"WorldInputNode ({self.name()}): Height calculation finished.")
        # else:
            # logger.debug(f"WorldInputNode ({self.name()}): Cache hit for compute.")

        # Всегда возвращаем кэш высоты (или нули, если он пуст)
        if self._result_cache_height is not None:
             # logger.debug(f"WorldInputNode ({self.name()}): _compute returning height cache.")
             # Используем self._result_cache для совместимости с базовым compute()
             self._result_cache = self._result_cache_height
             return self._result_cache
        else:
             logger.warning(f"WorldInputNode ({self.name()}): Height cache was unexpectedly None.")
             self._result_cache = np.zeros_like(context["x_coords"])
             return self._result_cache
