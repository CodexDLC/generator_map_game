# ==============================================================================
# Файл: editor/nodes/universal/noises/value_noise_node.py
# Назначение: Простая октава Value Noise. Диапазон: [0, 1].
# ==============================================================================

import numpy as np
from editor.nodes.base_node import GeneratorNode
from game_engine_restructured.numerics.fast_noise import value_noise_2d
from game_engine_restructured.numerics.field_packet import make_packet, SPACE_NORM

# --- Локализация ---
NODE_NAME_LBL   = "Value Noise"
IDENTIFIER_LBL  = "Универсальные.Шумы"
DESCRIPTION_TEXT = """
Генерирует одну сглаженную октаву Value Noise (диапазон [0, 1]).
Параметры:
  - Seed Offset: сдвиг сида для вариативности слоёв
  - Scale (tiles): масштаб карты в тайлах
  - Cell Size: характерный размер ячейки интерполяции
"""

# --- Метки UI ---
TAB_NOISE       = "Noise"
LBL_SEED_OFFSET = "Seed Offset"
LBL_SCALE       = "Scale (tiles)"
LBL_CELL_SIZE   = "Cell Size"

class ValueNoiseNode(GeneratorNode):
    __identifier__ = IDENTIFIER_LBL
    NODE_NAME = NODE_NAME_LBL

    def __init__(self):
        super().__init__()

        self.add_output('height')

        # Параметры
        self.add_text_input('seed_offset', LBL_SEED_OFFSET, tab=TAB_NOISE, text='0')
        self.add_text_input('scale_tiles', LBL_SCALE,      tab=TAB_NOISE, text='2000')
        self.add_text_input('cell_size',   LBL_CELL_SIZE,  tab=TAB_NOISE, text='4')

        self.set_color(30, 90, 90)
        self.set_description(DESCRIPTION_TEXT)

    # --- безопасные парсеры локально ---
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
        cell_size = max(self._as_int('cell_size', 4, min_value=1), 1)

        layer_seed = int(context.get('seed', 0)) + int(self.id, 0) + seed_offset
        freq = 1.0 / (scale * cell_size + 1e-6)

        x = context["x_coords"];
        z = context["z_coords"]
        h, w = x.shape
        noise = np.empty_like(x, dtype=np.float32)

        for j in range(h):
            for i in range(w):
                noise[j, i] = value_noise_2d(x[j, i] * freq, z[j, i] * freq, layer_seed)  # [0..1]

        norm01 = np.clip(noise.astype(np.float32, copy=False), 0.0, 1.0)
        pkt = make_packet(norm01, space=SPACE_NORM, ref_m=1.0, amp_m=None, bias_m=0.0)
        self._result_cache = pkt
        return pkt
