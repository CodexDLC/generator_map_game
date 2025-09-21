# nodes/surface_paint.py
from ..base import Node, Context, register

@register
class SurfacePaint(Node):
    type = "SurfacePaint"
    default_params = {"sea_level_m": 300.0}

    def apply(self, ctx: Context, inputs):
        H = inputs["height"]
        # surfaces = paint_surfaces(H, self.params)  # вызов твоей логики
        surfaces = None
        return {"height": H, "surfaces": surfaces}
