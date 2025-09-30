# ==============================================================================
# Файл: editor/nodes/height/io/world_input_node.py
# ВЕРСИЯ 5.0 (ТВОРЧЕСКИЙ РЕФАКТОРИНГ): Нода теперь является просто точкой входа.
# - Логика генерации шума полностью удалена из ноды.
# ==============================================================================

import logging
import numpy as np
from editor.nodes.base_node import GeneratorNode

logger = logging.getLogger(__name__)

IDENTIFIER_LBL = "Ландшафт.Пайплайн"
NODE_NAME_LBL  = "World Input"

DESCRIPTION_TEXT = """
Точка входа для графа. Предоставляет базовый шум, сгенерированный
на основе глобальных настроек мира в главном окне.
"""

class WorldInputNode(GeneratorNode):
    __identifier__ = IDENTIFIER_LBL
    NODE_NAME = NODE_NAME_LBL

    def __init__(self):
        super().__init__()
        self.add_output("height")
        self.set_color(80, 25, 30)
        self.set_description(DESCRIPTION_TEXT)

    # --- ИЗМЕНЕНИЕ: _compute теперь просто возвращает подготовленный шум из контекста ---
    def _compute(self, context):
        # Эта нода теперь просто возвращает базовый шум из контекста,
        # который будет подготовлен в главном окне.
        base_noise = context.get("world_input_noise", np.zeros_like(context["x_coords"]))
        return base_noise
