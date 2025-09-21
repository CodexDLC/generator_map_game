# nodes/mountains.py
import numpy as np
from ..base import Node, Context, register

@register
class Mountains(Node):
    type = "Mountains"
    default_params = {"amp_m": 380.0, "ridge": True}

    def apply(self, ctx: Context, inputs):
        H = inputs["height"].copy()
        # ↓ тут просто вызов твоей функции «добавить горный слой» к H
        # H = add_mountains(H, self.params, seed=ctx.world_seed)
        return {"height": H}
