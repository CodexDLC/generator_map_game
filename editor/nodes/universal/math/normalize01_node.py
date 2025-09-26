from __future__ import annotations
import numpy as np
from editor.nodes.base_node import GeneratorNode
from game_engine_restructured.numerics.normalization import normalize01

# Локализуемые константы
IDENTIFIER_LBL   = "Универсальные.Математика"
NODE_NAME_LBL    = "Normalize [0..1]"
DESCRIPTION_TEXT = (
    "Гарантирует чистый шум в диапазоне [0..1], независимо от входа: метры, [-1..1], суммы >1, NaN. "
    "Есть режимы: auto/minmax/symmetric/clamp01/percentile и опциональное округление до N знаков."
)

class Normalize01Node(GeneratorNode):
    __identifier__ = IDENTIFIER_LBL
    NODE_NAME = NODE_NAME_LBL

    def __init__(self):
        super().__init__()
        self.add_input('height_in')   # что угодно
        self.add_output('height')     # строго [0..1]

        # Простые свойства через текст/чекбокс (держим совместимость API)
        self.add_text_input('mode',          "Mode (auto/minmax/symmetric/clamp01/percentile)", tab="Normalize", text="auto")
        self.add_text_input('min_override',  "Min Override (blank=auto)",                        tab="Normalize", text="")
        self.add_text_input('max_override',  "Max Override (blank=auto)",                        tab="Normalize", text="")
        self.add_text_input('p_low',         "Percentile Low (0..100)",                          tab="Percentile", text="1")
        self.add_text_input('p_high',        "Percentile High (0..100)",                         tab="Percentile", text="99")
        self.add_checkbox  ('clip_after',    "Clip to [0..1] after",                             tab="Output", state=True)
        self.add_text_input('decimals',      "Round Decimals (0=no round)",                      tab="Output", text="0")
        self.add_text_input('nan_fill',      "NaN Fill",                                         tab="Safety", text="0")
        self.add_text_input('fill_const',    "Fallback Const (flat)",                            tab="Safety", text="0")

        self.set_color(30, 30, 90)
        self.set_description(DESCRIPTION_TEXT)

    def _f(self, name, default):
        v = self.get_property(name)
        try:
            if v in ("", None): return default
            return float(v)
        except (TypeError, ValueError):
            return default

    def _i(self, name, default, mn=None):
        v = self.get_property(name)
        try:
            x = int(float(v))
            if mn is not None: x = max(x, mn)
            return x
        except (TypeError, ValueError):
            return default

    def _compute(self, context):
        port = self.get_input('height_in')
        if not (port and port.connected_ports()):
            out = np.zeros_like(context["x_coords"], dtype=np.float32)
            self._result_cache = out
            return out

        X = port.connected_ports()[0].node().compute(context)

        mode = (self.get_property('mode') or "auto").strip().lower()
        min_ov = self.get_property('min_override');
        min_ov = None if (min_ov in ("", None)) else float(min_ov)
        max_ov = self.get_property('max_override');
        max_ov = None if (max_ov in ("", None)) else float(max_ov)
        p_low = float(self.get_property('p_low') or 1.0)
        p_high = float(self.get_property('p_high') or 99.0)

        kwargs_common = dict(
            mode=mode, min_override=min_ov, max_override=max_ov,
            clip_after=bool(self.get_property('clip_after')),
            decimals=int(float(self.get_property('decimals') or 0)),
            nan_fill=float(self.get_property('nan_fill') or 0.0),
            fill_const=float(self.get_property('fill_const') or 0.0),
        )

        try:
            # пробуем “новую” сигнатуру (с перцентилями)
            Y = normalize01(X, p_low=p_low, p_high=p_high, **kwargs_common)
        except TypeError:
            # совместимость со “старой” сигнатурой
            if mode == "percentile":
                # эмулируем percentile через minmax с руками посчитанными пределами
                lo = float(np.nanpercentile(X, p_low))
                hi = float(np.nanpercentile(X, p_high))
                Y = normalize01(X, mode="minmax", min_override=lo, max_override=hi,
                                **{k: v for k, v in kwargs_common.items() if
                                   k not in ("mode", "min_override", "max_override")})
            else:
                Y = normalize01(X, **kwargs_common)

        self._result_cache = Y.astype(np.float32, copy=False)
        return self._result_cache

