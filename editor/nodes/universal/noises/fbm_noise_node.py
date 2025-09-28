# ==============================================================================
# editor/nodes/universal/noises/fbm_noise_node.py
# ВЕРСИЯ 2.0: Без внутреннего варпа. Чистый источник FBM → packet [0..1].
# Поддержка scale_mode: tiles|meters.
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

        # чистый источник: только выход
        self.add_output("height")

        # параметры
        self.add_enum_input("scale_mode", "Scale Mode", ["tiles", "meters"], tab="Params", default="tiles")
        self.add_text_input("scale",      "Scale value", tab="Params", text="2000")  # tiles или meters в зависимости от mode

        self.add_text_input("octaves",    "Octaves",     tab="Params", text="4")
        self.add_text_input("gain",       "Gain (0..1)", tab="Params", text="0.5")
        self.add_text_input("lacunarity", "Lacunarity",  tab="Params", text="2.0")
        self.add_checkbox   ("ridge",     "Ridge",       tab="Params", state=False)

        self.add_text_input("seed_offset","Seed Offset", tab="Params", text="0")

        self.set_color(70, 50, 20)
        self.set_description(DESCRIPTION_TEXT)

    # ---------- helpers ----------
    def _f(self, name: str, default: float) -> float:
        v = self.get_property(name)
        try:
            if v in ("", None):
                return float(default)
            x = float(v)
            return x if np.isfinite(x) else float(default)
        except Exception:
            return float(default)

    def _i(self, name: str, default: int, mn: int | None = None) -> int:
        v = self.get_property(name)
        try:
            x = int(float(v))
            if mn is not None:
                x = max(x, mn)
            return x
        except Exception:
            return default

    # ---------- compute ----------
    def _compute(self, context):
        # sanity: координаты
        x = context.get("x_coords"); z = context.get("z_coords")
        if not (isinstance(x, np.ndarray) and isinstance(z, np.ndarray) and x.ndim == 2 and x.shape == z.shape):
            logger.error("FBMNoiseNode: некорректные координаты в контексте; отдаю нули 256x256.")
            out = np.zeros((256, 256), dtype=np.float32)
            pkt = make_packet(out, space=SPACE_NORM, ref_m=1.0, amp_m=None, bias_m=0.0)
            self._result_cache = pkt
            return pkt

        H, W     = x.shape
        seed     = int(context.get("seed", 0))
        so       = self._i("seed_offset", 0)
        layer_sd = (seed + int(self.id, 0) + so) & 0xFFFFFFFF

        scale_mode = self._enum("scale_mode", ["tiles", "meters"], "tiles")
        scale      = max(self._f("scale", 2000.0), 1e-6)

        if scale_mode == "tiles":
            cell_size = float(context.get("cell_size", 1.0))
            freq0 = 1.0 / (scale * cell_size + 1e-6)
        else:  # "meters"
            freq0 = 1.0 / (scale + 1e-6)

        octaves    = self._i("octaves", 4, mn=1)
        gain       = float(np.clip(self._f("gain", 0.5), 0.0, 1.0))
        lacunarity = max(self._f("lacunarity", 2.0), 1.0)
        ridge      = bool(self.get_property("ridge"))

        # fbm в диапазоне примерно [-max_amp..max_amp], но реализация отдаёт уже «биполярный» шум
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

        # нормируем по суммарной амплитуде
        max_amp = fbm_amplitude(gain, octaves)
        nrm = raw / max_amp if max_amp > 1e-6 else raw
        # в [0..1]
        n01 = (np.clip(nrm, -1.0, 1.0) + 1.0) * 0.5
        n01 = n01.astype(np.float32, copy=False)

        pkt = make_packet(n01, space=SPACE_NORM, ref_m=1.0, amp_m=None, bias_m=0.0)
        self._result_cache = pkt
        return pkt
