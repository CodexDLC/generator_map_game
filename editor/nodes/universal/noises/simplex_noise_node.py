# ==============================================================================
# Файл: editor/nodes/universal/noises/simplex_noise_node.py
# Назначение: Simplex noise. Диапазон [-1, 1].
# ==============================================================================

import numpy as np
from editor.nodes.base_node import GeneratorNode
from opensimplex import OpenSimplex

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

        self.add_text_input('seed_offset', LBL_SEED_OFFSET, tab=TAB_NOISE, text='0')
        self.add_text_input('scale_tiles', LBL_SCALE,      tab=TAB_NOISE, text='2000')

        self.set_color(90, 30, 90)
        self.set_description(DESCRIPTION_TEXT)

    def _as_float(self, name, default):
        try: return float(self.get_property(name))
        except (TypeError, ValueError): return default

    def _as_int(self, name, default, min_value=None):
        try:
            v = int(float(self.get_property(name)))
            return max(v, min_value) if min_value is not None else v
        except (TypeError, ValueError):
            return default

    def _compute(self, context):
        seed_offset = self._as_int('seed_offset', 0)
        scale = max(self._as_float('scale_tiles', 2000.0), 1e-6)

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
