# editor/nodes/height/io/output_node.py
# ВЕРСИЯ 5.0: Совместимо с новой базовой нодой (compact/expanded + группы),
#             безопасно без входа, параметры видны в правой панели.
import logging
import numpy as np

from editor.nodes.base_node import GeneratorNode
from game_engine_restructured.numerics.field_packet import (
    get_data, get_space, make_packet, SPACE_NORM, SPACE_METR
)

logger = logging.getLogger(__name__)

IDENTIFIER_LBL   = "Ландшафт.Пайплайн"
NODE_NAME_LBL    = "Output Height"
DESCRIPTION_TEXT = """
Финальная нода пайплайна: принимает карту (field_packet или [0..1]),
переводит в метры, умножая на Max Height (m). Возвращает packet в SPACE_METR.
"""

class OutputNode(GeneratorNode):
    __identifier__ = IDENTIFIER_LBL
    NODE_NAME = NODE_NAME_LBL

    def __init__(self):
        super().__init__()

        # Порты
        self.add_input('height')

        # Свойства (таб = 'Params', группы — для аккордеон-панели)
        self.add_text_input(
            name='height_max_m', label='Max Height (m)',
            text='1000', tab='Params', group='Output'
        )
        self.add_text_input(
            name='sea_level_m', label='Sea Level (m)',
            text='0', tab='Params', group='Preview'
        )
        self.add_checkbox(
            name='preview_with_offset', label='Preview: apply Sea Level',
            state=False, tab='Params', group='Preview'
        )

        # (необязательно) дефолтные флаги секций — если хочешь, чтобы они были включены
        try:
            self.set_property('grp_Output__enabled', True)
            self.set_property('grp_Preview__enabled', True)
        except Exception:
            pass

        self.set_color(25, 80, 30)
        self.set_description(DESCRIPTION_TEXT)

    # --- вычисления ---------------------------------------------------------

    def _compute(self, context: dict):
        # Безопасно читаем вход: если не подключен — вернём нули в метрах
        port = self.get_input('height')
        conns = port.connected_ports()
        world_max = self._f('height_max_m', 1000.0)

        if not conns:
            shape = getattr(context.get('x_coords'), 'shape', (256, 256))
            zeros = np.zeros(shape, dtype=np.float32)
            pkt = make_packet(zeros, space=SPACE_METR, ref_m=world_max, amp_m=world_max)
            self._result_cache = pkt
            return pkt

        # Вычисляем апстрим
        upstream = conns[0].node().compute(context)

        # Достаём массив и его «пространство»
        space = get_space(upstream, default=SPACE_NORM)
        arr = get_data(upstream).astype(np.float32, copy=False)

        if space == SPACE_NORM:
            height_m = np.clip(arr, 0.0, 1.0) * world_max
        else:
            # уже в метрах — не переумножаем
            height_m = arr

        # В предпросмотре можно «опустить/поднять» уровень моря (визуально)
        bias = 0.0
        if bool(self.get_property('preview_with_offset')):
            sea = self._f('sea_level_m', 0.0)
            height_m = height_m - sea
            bias = -sea  # для корректной упаковки packet'а

        pkt = make_packet(
            height_m,
            space=SPACE_METR,
            ref_m=world_max,
            amp_m=world_max,
            bias_m=bias
        )
        self._result_cache = pkt
        return pkt
