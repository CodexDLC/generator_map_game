# ==============================================================================
# Файл: editor/nodes/universal/noises/voronoi_noise_node.py
# ВЕРСИЯ 2.0 (РЕФАКТОРИНГ): Использует get_property из базового класса.
# ==============================================================================

import numpy as np
from editor.nodes.base_node import GeneratorNode
from game_engine_restructured.numerics.fast_noise import voronoi_grid
from game_engine_restructured.numerics.field_packet import make_packet, SPACE_NORM

# --- Локализация ---
NODE_NAME_LBL   = "Voronoi Noise"
IDENTIFIER_LBL  = "Универсальные.Шумы"
DESCRIPTION_TEXT = """
Генерирует ячеистый Voronoi noise (диапазон [0, 1]).
Параметры:
  - Seed Offset
  - Scale (tiles)
  - Cell Size
"""

TAB_NOISE       = "Noise"
LBL_SEED_OFFSET = "Seed Offset"
LBL_SCALE       = "Scale (tiles)"
LBL_CELL_SIZE   = "Cell Size"

class VoronoiNoiseNode(GeneratorNode):
    __identifier__ = IDENTIFIER_LBL
    NODE_NAME = NODE_NAME_LBL

    def __init__(self):
        super().__init__()
        self.add_output('height')

        # РЕФАКТОРИНГ: Указываем типы для авто-преобразования
        self._prop_meta["seed_offset"] = {'type': 'int', 'label': LBL_SEED_OFFSET, 'tab': TAB_NOISE, 'group': TAB_NOISE}
        self.add_text_input('seed_offset', LBL_SEED_OFFSET, tab=TAB_NOISE, text='0')

        self._prop_meta["scale_tiles"] = {'type': 'float', 'label': LBL_SCALE, 'tab': TAB_NOISE, 'group': TAB_NOISE}
        self.add_text_input('scale_tiles', LBL_SCALE,      tab=TAB_NOISE, text='2000')

        self._prop_meta["cell_size"] = {'type': 'int', 'label': LBL_CELL_SIZE, 'tab': TAB_NOISE, 'group': TAB_NOISE}
        self.add_text_input('cell_size',   LBL_CELL_SIZE,  tab=TAB_NOISE, text='4')

        self.set_color(90, 90, 30)
        self.set_description(DESCRIPTION_TEXT)

    # РЕФАКТОРИНГ: Вспомогательные методы _as_float и _as_int больше не нужны

    def _compute(self, context):
        # РЕФАКТОРИНГ: Прямое использование get_property()
        seed_offset = self.get_property('seed_offset')
        scale = max(self.get_property('scale_tiles'), 1e-6)
        cell_size = max(self.get_property('cell_size'), 1)

        layer_seed = int(context.get('seed', 0)) + int(self.id, 0) + seed_offset
        freq = 1.0 / (scale * cell_size + 1e-6)

        noise = voronoi_grid(seed=layer_seed,
                             coords_x=context["x_coords"],
                             coords_z=context["z_coords"],
                             freq0=freq)
        if noise is None:
            noise = np.zeros_like(context['x_coords'], dtype=np.float32)

        norm01 = np.clip(noise.astype(np.float32, copy=False), 0.0, 1.0)
        pkt = make_packet(norm01, space=SPACE_NORM, ref_m=1.0, amp_m=None, bias_m=0.0)
        self._result_cache = pkt
        return pkt
