# ==============================================================================
# Файл: editor/nodes/generator/modules/warp_node.py
# ВЕРСИЯ 2.0: Полное описание, раздельные амплитуды X/Z, безопасный парсинг,
#             sanity-check формы, независимые сиды по осям.
# ==============================================================================
from __future__ import annotations
import numpy as np
from editor.nodes.base_node import GeneratorNode
from game_engine_restructured.algorithms.terrain.steps.noise import _generate_noise_field


class WarpNode(GeneratorNode):
    """
    Категория (palette): Ландшафт.Модули
    Роль: Поле варпа (смещения координат) для других нод

    Входы:  — нет (генерирует поле сам)
    Выходы:
      - warp_field : dict с ключами
          'warp_x' : np.ndarray (смещение по X в метрах, H×W)
          'warp_z' : np.ndarray (смещение по Z в метрах, H×W)

    Параметры:
      [Warp Settings]
        - Amplitude X (m) (float>=0) : максимальная сила смещения по X
        - Amplitude Z (m) (float>=0) : максимальная сила смещения по Z
        - Scale (tiles)   (float>0)  : крупномасштабный размер «вихрей»
        - Octaves         (int>=1)   : детализация
        - Ridge (bool)               : гребневой характер смещения (экспериментально)

    Поведение:
      - Для независимости направлений используются разные seed_offset по осям.
      - Формы 'warp_x'/'warp_z' всегда совпадают с формой контекстных координат.
    """

    __identifier__ = 'Ландшафт.Модули'
    NODE_NAME = 'Warp'

    def __init__(self):
        super().__init__()
        self.add_output('warp_field', 'Out')

        self.add_text_input('amp_x',       'Amplitude X (m)', tab='Warp Settings', text='200.0')
        self.add_text_input('amp_z',       'Amplitude Z (m)', tab='Warp Settings', text='200.0')
        self.add_text_input('scale_tiles', 'Scale (tiles)',   tab='Warp Settings', text='4000')
        self.add_text_input('octaves',     'Octaves',         tab='Warp Settings', text='2')
        self.add_checkbox('ridge',         'Ridge',           tab='Warp Settings', state=False)

        self.set_color(25, 80, 30)

        self.set_description("""
        Генерирует двухкомпонентное поле смещений координат (warp_x/warp_z).
        Подключите выход этой ноды к входу Warp любой ноды, поддерживающей варп,
        например — к Noise.

        Советы:
          • Большой Scale (tiles) даёт плавные «речки» смещения.
          • Разные амплитуды X/Z позволяют тянуть рельеф в предпочтительном направлении.
          • Ridge может дать «гребневую» структуру в смещении (пробовать осторожно).
        """)

    # ---------------------------- ВНУТРЕННИЕ ХЕЛПЕРЫ ----------------------------

    def _as_float(self, name: str, default: float) -> float:
        v = self.get_property(name)
        try:
            x = float(v)
            if not np.isfinite(x):
                return default
            return max(x, 0.0)
        except (TypeError, ValueError):
            return default

    def _as_int(self, name: str, default: int, min_value: int | None = None) -> int:
        v = self.get_property(name)
        try:
            i = int(float(v))
            if min_value is not None:
                i = max(i, min_value)
            return i
        except (TypeError, ValueError):
            return default

    # -------------------------------- COMPUTE -----------------------
