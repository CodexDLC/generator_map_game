# ==============================================================================
# Файл: editor/nodes/height/io/world_input_node.py
# ВЕРСИЯ 6.0: Добавлен второй выход для маски смешивания гексов.
# ==============================================================================

import logging
import numpy as np
from editor.nodes.base_node import GeneratorNode
# --- ДОБАВЛЯЕМ ИМПОРТ ---
from NodeGraphQt import Port

logger = logging.getLogger(__name__)

IDENTIFIER_LBL = "Ландшафт.Пайплайн"
NODE_NAME_LBL  = "World Input"

# --- ОБНОВЛЯЕМ ОПИСАНИЕ ---
DESCRIPTION_TEXT = """
Точка входа для графа. Предоставляет базовый ландшафт,
сгенерированный путем смешивания данных из глобальной гексагональной сетки,
а также маску смешивания (вес ближайшего гекса).
"""

class WorldInputNode(GeneratorNode):
    __identifier__ = IDENTIFIER_LBL
    NODE_NAME = NODE_NAME_LBL

    def __init__(self):
        super().__init__()
        self.add_output("height")
        # --- ДОБАВЛЯЕМ ВТОРОЙ ВЫХОД ---
        self.add_output("mask")
        # --- КОНЕЦ ИЗМЕНЕНИЯ ---
        self.set_color(80, 25, 30)
        self.set_description(DESCRIPTION_TEXT)

        # --- ДОБАВЛЯЕМ КЭШИ ДЛЯ ДВУХ ВЫХОДОВ ---
        self._result_cache_height: np.ndarray | None = None
        self._result_cache_mask: np.ndarray | None = None
        self._last_context_signature_computed = None
        # --- КОНЕЦ ИЗМЕНЕНИЯ ---

    # --- МОДИФИЦИРУЕМ _compute ---
    def _compute(self, context):
        # Эта функция теперь вызывается только ОДИН РАЗ за цикл вычислений,
        # даже если запрашиваются оба выхода. Она подготовит оба результата.

        # Проверяем, не вычисляли ли мы уже для этого же контекста
        current_context_signature = id(context) # Простой способ проверить идентичность контекста
        if not self._is_dirty and self._last_context_signature_computed == current_context_signature:
             # Результаты уже в кэше, ничего не делаем
             # logger.debug(f"WorldInputNode ({self.name()}): Cache hit based on context signature.")
             pass # Явно ничего не возвращаем, compute_outputs сделает свое дело
        else:
            logger.debug(f"WorldInputNode ({self.name()}): Recalculating height and mask...")
            # Получаем оба результата из контекста, подготовленные в preview_logic
            self._result_cache_height = context.get("world_input_height", np.zeros_like(context["x_coords"]))
            self._result_cache_mask = context.get("world_input_mask", np.ones_like(context["x_coords"])) # По умолчанию маска = 1

            # Копируем, чтобы избежать проблем с памятью
            self._result_cache_height = self._result_cache_height.copy()
            self._result_cache_mask = self._result_cache_mask.copy()

            self._last_context_signature_computed = current_context_signature
            # self.mark_dirty(False) # compute_outputs сделает это

        # Важно: _compute больше не возвращает результат напрямую!
        # Вместо этого мы переопределим метод compute_outputs
        return self._result_cache_height

    # --- ДОБАВЛЯЕМ НОВЫЙ МЕТОД ---
    def compute_outputs(self, context, requested_port: Port) -> np.ndarray | None:
        """
        Этот метод вызывается движком графа для КАЖДОГО выходного порта,
        когда результат действительно нужен.
        """
        # Сначала убедимся, что _compute был вызван и данные готовы в кэше
        # (Проверка _is_dirty нужна, чтобы _compute точно отработал хотя бы раз)
        if self._is_dirty or self._last_context_signature_computed != id(context):
             self._compute(context)
             self._is_dirty = False # Сбрасываем флаг после вычисления

        # Возвращаем нужный кэш в зависимости от порта
        if requested_port.name() == "height":
            # logger.debug(f"WorldInputNode ({self.name()}): Providing height cache.")
            return self._result_cache_height
        elif requested_port.name() == "mask":
            # logger.debug(f"WorldInputNode ({self.name()}): Providing mask cache.")
            return self._result_cache_mask
        else:
            # На случай, если появятся другие выходы
            return None
    # --- КОНЕЦ НОВОГО МЕТОДА ---