# ==============================================================================
# editor/nodes/height/io/output_node.py
# ВЕРСИЯ 4.5: Упрощена архитектура - только один вход, один выход.
#             Последняя нода в пайплайне, поэтому input/output симметрично не нужны.
# ==============================================================================
import logging
import numpy as np
from editor.nodes.base_node import GeneratorNode
from game_engine_restructured.numerics.field_packet import get_data, get_space, to_meters, SPACE_NORM, SPACE_METR, make_packet

logger = logging.getLogger(__name__)

IDENTIFIER_LBL   = "Ландшафт.Пайплайн"
NODE_NAME_LBL    = "Output Height"
DESCRIPTION_TEXT = """
Финальная нода пайплайна: принимает карту (field_packet или [0..1]), переводит в метры,
умножает на max высоту (м). Возвращает данные в метрах для предпросмотра и передачи в другие системы.
"""

class OutputNode(GeneratorNode):
    __identifier__ = IDENTIFIER_LBL
    NODE_NAME = NODE_NAME_LBL

    def __init__(self):
        super().__init__()
        self.add_input('height')       # единственный вход: field_packet или [0..1] массив
        # UI свойства
        self.add_text_input('height_max_m', "Max Height (m)", tab="Params", text="1000")
        self.add_text_input('sea_level_m',  "Sea Level (m)",   tab="Params", text="0")
        self.add_checkbox('preview_with_offset', "Preview: apply Sea Level", tab="Params", state=False)
        self.set_color(25, 80, 30)
        self.set_description(DESCRIPTION_TEXT)

    def _as_float(self, name, default):
        try:
            return float(self.get_property(name))
        except (TypeError, ValueError):
            return default

    def _compute(self, context):
        port = self.get_input('height')
        inp = port.connected_ports()[0].node().compute(context)

        world_max = self._as_float('height_max_m', 1000.0)

        space = get_space(inp, default=SPACE_NORM)
        arr = get_data(inp)

        if space == SPACE_NORM:
            # вход – нормаль [0..1] → просто умножаем на потолок мира
            height01 = np.clip(arr.astype(np.float32, copy=False), 0.0, 1.0)
            height_m = height01 * world_max
        else:
            # вход – метры → НИЧЕГО больше не умножаем
            height_m = arr.astype(np.float32, copy=False)

        if bool(self.get_property('preview_with_offset')):
            height_m = height_m - self._as_float('sea_level_m', 0.0)

        pkt = make_packet(height_m, space=SPACE_METR, ref_m=world_max, amp_m=world_max,
                          bias_m=(-self._as_float('sea_level_m', 0.0) if bool(
                              self.get_property('preview_with_offset')) else 0.0))
        self._result_cache = pkt
        return pkt
