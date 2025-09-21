# nodes/stamp_rim.py
import numpy as np
from PIL import Image
from ..base import Node, Context, register
from ..sampler import poisson_cells
from ..stateless_rng import hash32

def load_brush(path: str) -> np.ndarray:
    im = Image.open(path).convert("L")
    arr = np.asarray(im, dtype=np.float32)/255.0
    return arr

@register
class StampRim(Node):
    type = "StampRim"
    default_params = {
        "brush": "res://assets/terrain_brushes/soft_ridges_1024.png",
        "radius_px": 420, "strength_m": 32.0, "blend": "max"
    }

    def apply(self, ctx: Context, inputs):
        H = inputs["height"].copy()
        brush = load_brush(self.params["brush"])
        centers = poisson_cells(ctx.region_rect, self.params["radius_px"],
                                layer_seed=hash32(0,0, self._layer_seed(ctx)))
        # ↓ здесь вызови твой уже написанный код штамповки (одиночные крупные «печати»)
        # apply_stamps(H, brush, centers, strength=self.params["strength_m"], blend=self.params["blend"])
        return {"height": H}

    def _layer_seed(self, ctx: Context) -> int:
        return hash32(1234567, 890123, ctx.world_seed)
