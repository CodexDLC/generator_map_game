# ==============================================================================
# Файл: editor/nodes/slope_mask_node.py
# Роль: Маска по уклону (углу наклона поверхности) из входной карты высот.
#       Угол задаётся в градусах, есть мягкость краёв (falloff) и инверсия.
# ==============================================================================

from __future__ import annotations
import numpy as np
from editor.nodes.base_node import GeneratorNode


def _smoothstep(edge0, edge1, x):
    # классическая smoothstep; защищаемся от edge1 == edge0
    denom = max(float(edge1 - edge0), 1e-9)
    t = np.clip((x - edge0) / denom, 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


class SlopeMaskNode(GeneratorNode):
    """
    Категория: Ландшафт.Маски
    Роль: Маска по уклону (в градусах) из входной карты высот.

    Вход:
      0) Height In — карта высот (H×W, метры)

    Выход:
      - Mask (0..1)

    Параметры:
      [Slope]
        - Min Angle (deg)   : нижняя граница диапазона
        - Max Angle (deg)   : верхняя граница диапазона
        - Edge Softness (°) : ширина плавного перехода (falloff) около границ
        - Invert            : инвертировать маску

    Формирование маски:
      θ = arctan(|∇h|), где |∇h| = sqrt( (dh/dx)^2 + (dh/dz)^2 ),
      dh/dx, dh/dz считаются через np.gradient(..., spacing=cell_size).
      Маска ≈ smoothstep(min−s, min+s, θ) * (1 − smoothstep(max−s, max+s, θ)).
    """

    __identifier__ = 'Ландшафт.Маски'
    NODE_NAME = 'Slope Mask'

    def __init__(self):
        super().__init__()

        self.add_input('Height In', 'In')
        self.add_output('Mask', 'Out')

        self.add_text_input('min_deg', 'Min Angle (deg)',   tab='Slope', text='10.0')
        self.add_text_input('max_deg', 'Max Angle (deg)',   tab='Slope', text='45.0')
        self.add_text_input('soft_deg','Edge Softness (°)', tab='Slope', text='4.0')
        self.add_checkbox('invert',    'Invert',            tab='Slope', state=False)

        self.set_color(80, 80, 30)
        self.set_description("""
        Строит маску по уклону поверхности.
        Угол θ берётся как arctan(|∇h|) в градусах. Диапазон [Min..Max] даёт 1.0,
        с плавными краями шириной ±Edge Softness. Можно инвертировать.
        """)

    # ---------- helpers ----------

    def _as_float(self, name: str, default: float) -> float:
        try:
            x = float(self.get_property(name))
            if not np.isfinite(x):
                return default
            return x
        except Exception:
            return default

    # ---------- compute ----------

    def compute(self, context):
        in_port = self.get_input(0)
        if not in_port or not in_port.connected_ports():
            # без высоты смысла нет — возвращаем нули
            shape = context['x_coords'].shape
            m = np.zeros(shape, dtype=float)
            self._result_cache = m
            return self._result_cache

        hmap = in_port.connected_ports()[0].node().compute(context)
        if not isinstance(hmap, np.ndarray):
            shape = context['x_coords'].shape
            hmap = np.zeros(shape, dtype=float)

        # Параметры
        amin = self._as_float('min_deg', 10.0)
        amax = self._as_float('max_deg', 45.0)
        soft = max(self._as_float('soft_deg', 4.0), 0.0)
        if amax < amin:
            amin, amax = amax, amin

        # Градиенты с учётом физических единиц
        cell = float(context.get('cell_size', 1.0))
        dz, dx = np.gradient(hmap, cell, cell)  # порядок: (по оси0, по оси1) = (z, x)
        slope = np.hypot(dx, dz)               # |∇h|
        angle = np.degrees(np.arctan(slope))   # θ в градусах

        # Плавные пороги
        lower = _smoothstep(amin - soft, amin + soft, angle)
        upper = 1.0 - _smoothstep(amax - soft, amax + soft, angle)
        mask = np.clip(lower * upper, 0.0, 1.0)

        if bool(self.get_property('invert')):
            mask = 1.0 - mask

        self._result_cache = mask
        return self._result_cache
