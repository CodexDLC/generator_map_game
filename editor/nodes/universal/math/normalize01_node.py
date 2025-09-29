# ==============================================================================
# Файл: editor/nodes/universal/math/normalize01_node.py
# ВЕРСИЯ 2.0 (РЕФАКТОРИНГ): Использует get_property из базового класса.
# ==============================================================================

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
        self.add_input('height_in')
        self.add_output('height')

        # РЕФАКТОРИНГ: Указываем типы для авто-преобразования
        self.add_text_input('mode',          "Mode (auto/minmax/symmetric/clamp01/percentile)", tab="Normalize", text="auto")
        self.add_text_input('min_override',  "Min Override (blank=auto)",                        tab="Normalize", text="")
        self.add_text_input('max_override',  "Max Override (blank=auto)",                        tab="Normalize", text="")
        
        self._prop_meta["p_low"] = {'type': 'float', 'label': "Percentile Low (0..100)", 'tab': "Percentile", 'group': "Percentile"}
        self.add_text_input('p_low',         "Percentile Low (0..100)",                          tab="Percentile", text="1")

        self._prop_meta["p_high"] = {'type': 'float', 'label': "Percentile High (0..100)", 'tab': "Percentile", 'group': "Percentile"}
        self.add_text_input('p_high',        "Percentile High (0..100)",                         tab="Percentile", text="99")

        self.add_checkbox  ('clip_after',    "Clip to [0..1] after",                             tab="Output", state=True)

        self._prop_meta["decimals"] = {'type': 'int', 'label': "Round Decimals (0=no round)", 'tab': "Output", 'group': "Output"}
        self.add_text_input('decimals',      "Round Decimals (0=no round)",                      tab="Output", text="0")

        self._prop_meta["nan_fill"] = {'type': 'float', 'label': "NaN Fill", 'tab': "Safety", 'group': "Safety"}
        self.add_text_input('nan_fill',      "NaN Fill",                                         tab="Safety", text="0")

        self._prop_meta["fill_const"] = {'type': 'float', 'label': "Fallback Const (flat)", 'tab': "Safety", 'group': "Safety"}
        self.add_text_input('fill_const',    "Fallback Const (flat)",                            tab="Safety", text="0")

        self.set_color(30, 30, 90)
        self.set_description(DESCRIPTION_TEXT)

    # РЕФАКТОРИНГ: Вспомогательные методы _f и _i больше не нужны

    def _compute(self, context):
        port = self.get_input('height_in')
        if not (port and port.connected_ports()):
            out = np.zeros_like(context["x_coords"], dtype=np.float32)
            self._result_cache = out
            return out

        X = port.connected_ports()[0].node().compute(context)

        # РЕФАКТОРИНГ: Используем get_property() где это возможно
        mode = self.get_property('mode') or "auto"
        p_low = self.get_property('p_low')
        p_high = self.get_property('p_high')
        decimals = self.get_property('decimals')
        nan_fill = self.get_property('nan_fill')
        fill_const = self.get_property('fill_const')
        clip_after = self.get_property('clip_after')

        # РЕФАКТОРИНГ: Оставляем локальную обработку для свойств, где пустая строка != 0
        min_ov_raw = super().get_property('min_override') # Берем сырое значение
        min_ov = None if (min_ov_raw in ("", None)) else float(min_ov_raw)
        
        max_ov_raw = super().get_property('max_override') # Берем сырое значение
        max_ov = None if (max_ov_raw in ("", None)) else float(max_ov_raw)

        kwargs_common = dict(
            mode=mode, min_override=min_ov, max_override=max_ov,
            clip_after=clip_after,
            decimals=decimals,
            nan_fill=nan_fill,
            fill_const=fill_const,
        )

        try:
            Y = normalize01(X, p_low=p_low, p_high=p_high, **kwargs_common)
        except TypeError:
            if mode == "percentile":
                lo = float(np.nanpercentile(X, p_low))
                hi = float(np.nanpercentile(X, p_high))
                Y = normalize01(X, mode="minmax", min_override=lo, max_override=hi,
                                **{k: v for k, v in kwargs_common.items() if
                                   k not in ("mode", "min_override", "max_override")})
            else:
                Y = normalize01(X, **kwargs_common)

        self._result_cache = Y.astype(np.float32, copy=False)
        return self._result_cache
