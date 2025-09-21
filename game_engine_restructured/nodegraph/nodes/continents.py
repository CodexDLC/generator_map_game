# nodes/continents.py
import numpy as np
from ..base import Node, Context, register

@register
class Continents(Node):
    type = "Continents"
    default_params = {"scale_tiles": 6000, "amp_m": 120.0, "octaves": 2}

    def apply(self, ctx: Context, inputs):
        size_px = ctx.region_rect[2]
        # ↓ вызови здесь твою функцию генерации континентального слоя
        # например: H = make_continents(size_px, self.params, seed=ctx.world_seed)
        H = np.zeros((size_px, size_px), dtype=np.float32)  # заглушка
        return {"height": H}
