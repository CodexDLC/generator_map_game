# ==============================================================================
# editor/nodes/universal/noises/fbm_noise_node.py
# ВЕРСИЯ 3.0 (АРХИТЕКТУРА): Используется новая система управления сидами.
# - Заменен add_text_input на add_seed_input для свойства seed_offset.
# ==============================================================================

from __future__ import annotations
import logging
import numpy as np

from editor.nodes.base_node import GeneratorNode
from game_engine_restructured.numerics.fast_noise import fbm_grid_bipolar, fbm_amplitude
from game_engine_restructured.numerics.field_packet import make_packet, SPACE_NORM

logger = logging.getLogger(__name__)

IDENTIFIER_LBL = "Универсальные.Шумы"
NODE_NAME_LBL  = "FBM Noise"

DESCRIPTION_TEXT = """
Источник FBM-шума. Выход — packet с нормалью [0..1] (space='norm01'), без метров.
Масштаб задаётся двумя способами:
  • Scale Mode = tiles  — Scale = размер в «тайлах» (учитывается cell_size из контекста)
  • Scale Mode = meters — Scale = физический размер в метрах

Для варпа используйте внешнюю ноду Domain Warp (Apply).
"""

class FBMNoiseNode(GeneratorNode):
    __identifier__ = IDENTIFIER_LBL
    NODE_NAME = NODE_NAME_LBL

    def __init__(self):
        super().__init__()
        self.add_output("height")
        self.add_enum_input("scale_mode", "Scale Mode", ["tiles", "meters"], tab="Params", default="tiles")
        
        self._prop_meta["scale"] = {'type': 'float', 'label': "Scale value", 'tab': "Params", 'group': "Params"}
        self.add_text_input("scale", "Scale value", tab="Params", text="2000")

        self._prop_meta["octaves"] = {'type': 'int', 'label': "Octaves", 'tab': "Params", 'group': "Params"}
        self.add_text_input("octaves", "Octaves", tab="Params", text="4")

        self._prop_meta["gain"] = {'type': 'float', 'label': "Gain (0..1)", 'tab': "Params", 'group': "Params"}
        self.add_text_input("gain", "Gain (0..1)", tab="Params", text="0.5")

        self._prop_meta["lacunarity"] = {'type': 'float', 'label': "Lacunarity", 'tab': "Params", 'group': "Params"}
        self.add_text_input("lacunarity", "Lacunarity", tab="Params", text="2.0")

        self.add_checkbox("ridge", "Ridge", tab="Params", state=False)

        # --- ИСПОЛЬЗУЕМ НОВЫЙ МЕТОД ДЛЯ СИДА ---
        self.add_seed_input("seed_offset", "Seed Offset", tab="Params", group="Params")
        # -------------------------------------

        self.set_color(70, 50, 20)
        self.set_description(DESCRIPTION_TEXT)

    # ---------- compute ----------
    def _compute(self, context):
        x = context.get("x_coords"); z = context.get("z_coords")
        if not (isinstance(x, np.ndarray) and isinstance(z, np.ndarray) and x.ndim == 2 and x.shape == z.shape):
            logger.error("FBMNoiseNode: некорректные координаты в контексте; отдаю нули 256x256.")
            out = np.zeros((256, 256), dtype=np.float32)
            pkt = make_packet(out, space=SPACE_NORM, ref_m=1.0, amp_m=None, bias_m=0.0)
            self._result_cache = pkt
            return pkt

        H, W     = x.shape
        seed     = int(context.get("seed", 0))
        
        # Теперь get_property вернет int, так как мы использовали add_seed_input
        so       = self.get_property("seed_offset")
        
        layer_sd = (seed + so + int(self.id, 0)) & 0xFFFFFFFF

        scale_mode = self.get_property("scale_mode")
        scale      = max(self.get_property("scale"), 1e-6)

        if scale_mode == "tiles":
            cell_size = float(context.get("cell_size", 1.0))
            freq0 = 1.0 / (scale * cell_size + 1e-6)
        else:  # "meters"
            freq0 = 1.0 / (scale + 1e-6)

        octaves    = max(self.get_property("octaves"), 1)
        gain       = float(np.clip(self.get_property("gain"), 0.0, 1.0))
        lacunarity = max(self.get_property("lacunarity"), 1.0)
        ridge      = self.get_property("ridge") # bool

        raw = fbm_grid_bipolar(seed=layer_sd,
                               coords_x=x, coords_z=z,
                               freq0=freq0,
                               octaves=octaves,
                               ridge=ridge,
                               gain=gain,
                               lacunarity=lacunarity)

        if not isinstance(raw, np.ndarray) or raw.shape != (H, W):
            logger.error("FBMNoiseNode: fbm_grid_bipolar вернул некорректный массив; нули.")
            out = np.zeros_like(x, dtype=np.float32)
            pkt = make_packet(out, space=SPACE_NORM, ref_m=1.0, amp_m=None, bias_m=0.0)
            self._result_cache = pkt
            return pkt

        max_amp = fbm_amplitude(gain, octaves)
        nrm = raw / max_amp if max_amp > 1e-6 else raw
        
        n01 = (np.clip(nrm, -1.0, 1.0) + 1.0) * 0.5
        n01 = n01.astype(np.float32, copy=False)

        pkt = make_packet(n01, space=SPACE_NORM, ref_m=1.0, amp_m=None, bias_m=0.0)
        self._result_cache = pkt
        return pkt
