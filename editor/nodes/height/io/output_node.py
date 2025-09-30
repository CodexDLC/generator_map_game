# ==============================================================================
# Файл: editor/nodes/height/io/output_node.py
# ВЕРСИЯ 6.0 (ТВОРЧЕСКИЙ РЕФАКТОРИНГ): Нода теперь является просто конечной точкой.
# - Вся логика масштабирования и преобразования в метры удалена.
# ==============================================================================

import logging
import numpy as np

from editor.nodes.base_node import GeneratorNode
from game_engine_restructured.numerics.field_packet import get_data

logger = logging.getLogger(__name__)

IDENTIFIER_LBL   = "Ландшафт.Пайплайн"
NODE_NAME_LBL    = "Output Height"

DESCRIPTION_TEXT = """
Финальная нода пайплайна. Принимает финальную карту высот в диапазоне [0..1].
Вся логика масштабирования и преобразования в метры теперь выполняется
в главном окне на основе глобальных настроек мира.
"""

class OutputNode(GeneratorNode):
    __identifier__ = IDENTIFIER_LBL
    NODE_NAME = NODE_NAME_LBL

    def __init__(self):
        super().__init__()
        self.add_input('height')
        # --- ИЗМЕНЕНИЕ: Все параметры удалены ---
        self.set_color(25, 80, 30)
        self.set_description(DESCRIPTION_TEXT)

    # --- ИЗМЕНЕНИЕ: _compute теперь просто возвращает результат из входа ---
    def _compute(self, context: dict):
        port = self.get_input('height')
        if not (port and port.connected_ports()):
            return np.zeros_like(context["x_coords"], dtype=np.float32)

        # Просто вычисляем вход и возвращаем его как есть (это будет массив 0..1)
        final_map_01 = port.connected_ports()[0].node().compute(context)
        self._result_cache = get_data(final_map_01) # Убеждаемся, что возвращаем чистый массив
        return self._result_cache
