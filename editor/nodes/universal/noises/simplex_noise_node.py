# ==============================================================================
# Файл: editor/nodes/universal/noises/simplex_noise_node.py
# ВЕРСИЯ 2.0 (РЕФАКТОРИНГ): Использует get_property из базового класса.
# ==============================================================================

import numpy as np
from editor.nodes.base_node import GeneratorNode
from opensimplex import OpenSimplex

from game_engine_restructured.numerics.field_packet import make_packet, SPACE_NORM

# --- Локализация ---
NODE_NAME_LBL   = "Simplex Noise"
IDENTIFIER_LBL  = "Универсальные.Шумы"
DESCRIPTION_TEXT = """
Генерирует 2D Simplex noise (диапазон [-1, 1]).
Параметры:
  - Seed Offset
  - Scale (tiles)
"""

TAB_NOISE       = "Noise"
LBL_SEED_OFFSET = "Seed Offset"
LBL_SCALE       = "Scale (tiles)"

class SimplexNoiseNode(GeneratorNode):
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

        self.set_color(90, 30, 90)
        self.set_description(DESCRIPTION_TEXT)

    # РЕФАКТОРИНГ: Вспомогательные методы _as_float и _as_int больше не нужны

    def _compute(self, context):
        # РЕФАКТОРИНГ: Прямое использование get_property()
        seed_offset = self.get_property('seed_offset')
        scale = max(self.get_property('scale_tiles'), 1e-6)

        layer_seed = int(context.get('seed', 0)) + int(self.id, 0) + seed_offset
        noise_generator = OpenSimplex(seed=layer_seed)
        freq = 1.0 / (scale + 1e-6)

        x_coords = context["x_coords"];
        z_coords = context["z_coords"]
        h, w = x_coords.shape
        noise = np.empty_like(x_coords, dtype=np.float32)

        for j in range(h):
            for i in range(w):
                cx = x_coords[j, i] * freq
                cz = z_coords[j, i] * freq
                noise[j, i] = noise_generator.noise2(x=cx, y=cz)  # [-1..1]

        # → [0..1] и packet
        norm01 = (np.clip(noise, -1.0, 1.0) + 1.0) * 0.5
        pkt = make_packet(norm01, space=SPACE_NORM, ref_m=1.0, amp_m=None, bias_m=0.0)
        self._result_cache = pkt
        return pkt
