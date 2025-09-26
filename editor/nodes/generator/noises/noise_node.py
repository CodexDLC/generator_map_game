# ==============================================================================
# Файл: editor/nodes/noise_node.py
# ВЕРСИЯ 5.0: Внешний Warp-вход удалён. Варп теперь встроен в ноду (по галочке).
#             Появились/скрываются поля настроек варпа. Безопасный парсинг.
#             Поддержка режимов смешения: add / subtract / multiply / replace.
# ==============================================================================
from __future__ import annotations
import numpy as np
from NodeGraphQt.constants import LayoutDirectionEnum

from editor.nodes.base_node import GeneratorNode
from game_engine_restructured.algorithms.terrain.steps.noise import _generate_noise_field


class NoiseNode(GeneratorNode):
    """
    Категория (palette): Ландшафт.Шумы
    Роль: Этап пайплайна — генерирует шум и (опционально) искривляет координаты (warp).

    Порты:
      Вход:
        0) Height In (опц.) — карта высот для смешения.
      Выход:
        - Height Out — 2D np.ndarray (карта высот, м).

    Параметры:
      [Noise]
        - Seed Offset (int)
        - Scale (tiles) (float>0)
        - Octaves (int>=1)
        - Amplitude (m) (float>=0)
        - Ridge (bool)

      [Blending]
        - Blend Mode: add | subtract | multiply | replace
          add/subtract  : prev ± noise
          multiply      : prev * (1 + noise/amp)  (если amp≈0 → prev)
          replace       : только noise (вход игнорируется)

      [Warp]
        - Enable Internal Warp (bool)
          (если включено — отображаются:)
            - Warp Amplitude X (m) (float>=0)
            - Warp Amplitude Z (m) (float>=0)
            - Warp Scale (tiles)   (float>0)
            - Warp Octaves         (int>=1)
            - Warp Ridge           (bool)

    Поведение:
      • При включённом внутреннем варпе координаты (x,z) локально смещаются перед
        генерацией шума: x' = x + warp_x, z' = z + warp_z.
      • При выключенном — варп не применяется.
    """

    __identifier__ = 'Ландшафт.Шумы'
    NODE_NAME = 'Noise'

    # ---------------------------- ЖИЗНЕННЫЙ ЦИКЛ ----------------------------

    def __init__(self):
        super().__init__()

        # --- ПОРТЫ ---
        self.add_input('Height In', 'Height In')   # порт 0
        self.add_output('Height Out', 'Out')

        self.add_checkbox('vertical_layout', 'Vertical Layout', tab='Noise', state=True)

        # --- ПАРАМЕТРЫ ШУМА ---
        self.add_text_input('seed_offset', 'Seed Offset',   tab='Noise', text='0')
        self.add_text_input('scale_tiles', 'Scale (tiles)', tab='Noise', text='1500')
        self.add_text_input('octaves',     'Octaves',       tab='Noise', text='5')
        self.add_text_input('amp_m',       'Amplitude (m)', tab='Noise', text='100')
        self.add_checkbox('ridge',         'Ridge',         tab='Noise', state=False)

        # --- ПАРАМЕТРЫ СМЕШЕНИЯ ---
        self.add_combo_menu('blend_mode', 'Blend Mode',
                            items=['add', 'subtract', 'multiply', 'replace'],
                            tab='Blending')

        # --- ВНУТРЕННИЙ WARP ---
        self.add_checkbox('use_internal_warp', 'Enable Internal Warp', tab='Warp', state=False)
        self.add_text_input('warp_amp_x',       'Warp Amplitude X (m)', tab='Warp', text='200.0')
        self.add_text_input('warp_amp_z',       'Warp Amplitude Z (m)', tab='Warp', text='200.0')
        self.add_text_input('warp_scale_tiles', 'Warp Scale (tiles)',   tab='Warp', text='4000')
        self.add_text_input('warp_octaves',     'Warp Octaves',         tab='Warp', text='2')
        self.add_checkbox('warp_ridge',         'Warp Ridge',           tab='Warp', state=False)

        # Визуал и описание
        self.set_color(30, 70, 110)
        self.set_description("""
        Генерирует шумовую карту высот. Встроенный варп включается галочкой:
        при активном варпе нода сама рассчитывает warp_x/warp_z и искривляет
        координаты перед генерацией шума. Если галочка снята — варп не применяется.
        """)

        # Сразу синхронизируем видимость полей внутреннего варпа
        self._sync_warp_widgets_visibility()

    # Чтобы при переключении галочки скрывать/показывать поля — перехватываем set_property
    def set_property(self, name, value, push_undo=False, **kw):
        res = super().set_property(name, value, push_undo=push_undo, **kw)
        if name == 'vertical_layout':
            from NodeGraphQt.constants import LayoutDirectionEnum
            self.set_layout_direction(
                LayoutDirectionEnum.VERTICAL.value if value
                else LayoutDirectionEnum.HORIZONTAL.value
            )
        return res

    # ---------------------------- UI-ХЕЛПЕРЫ ----------------------------

    def _sync_warp_widgets_visibility(self):
        """
        Прячет/показывает параметры внутреннего варпа в зависимости от чекбокса.
        Мягкая реализация: если обёртка не поддерживает set_hidden/setVisible — просто игнорируем.
        """
        enabled = bool(self.get_property('use_internal_warp'))
        for prop_name in ('warp_amp_x', 'warp_amp_z', 'warp_scale_tiles', 'warp_octaves', 'warp_ridge'):
            try:
                w = self.get_widget(prop_name)
                if hasattr(w, 'set_hidden'):
                    w.set_hidden(not enabled)
                elif hasattr(w, 'setVisible'):
                    w.setVisible(enabled)
            except Exception:
                pass

    # ---------------------------- ПАРСИНГ ----------------------------

    def _as_float(self, name: str, default: float, nonneg: bool = False, pos: bool = False) -> float:
        v = self.get_property(name)
        try:
            x = float(v)
            if not np.isfinite(x):
                return default
            if pos:
                x = max(x, 1e-6)
            elif nonneg:
                x = max(x, 0.0)
            return x
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

    # ---------------------------- COMPUTE ----------------------------

    def compute(self, context):
        # 1) Предыдущая карта (если понадобится для blend)
        prev_map = None
        in_port = self.get_input(0)
        if in_port and in_port.connected_ports():
            prev_map = in_port.connected_ports()[0].node().compute(context)

        # 2) Локальный контекст (возможен внутренний варп)
        local_ctx = context.copy()

        if bool(self.get_property('use_internal_warp')):
            wx, wz = self._make_internal_warp(local_ctx)
            if wx is not None and wz is not None:
                local_ctx['x_coords'] = local_ctx['x_coords'] + wx
                local_ctx['z_coords'] = local_ctx['z_coords'] + wz

        # 3) Параметры шума и генерация
        params = {
            "scale_tiles": self._as_float('scale_tiles', 1500.0, pos=True),
            "octaves":     self._as_int('octaves', 5, min_value=1),
            "ridge":       bool(self.get_property('ridge')),
            "amp_m":       self._as_float('amp_m', 100.0, nonneg=True),
            "seed_offset": self._as_int('seed_offset', 0),
            "additive_only": True,  # совместимость с ядром
        }

        noise_map = _generate_noise_field(params, local_ctx)
        if noise_map is None:
            noise_map = np.zeros_like(local_ctx['x_coords'], dtype=float)

        # 4) Смешение
        mode = self.get_property('blend_mode') or 'add'
        if mode == 'replace':
            final_map = noise_map
        else:
            if prev_map is None:
                prev_map = np.zeros_like(noise_map, dtype=float)

            if mode == 'add':
                final_map = prev_map + noise_map
            elif mode == 'subtract':
                final_map = prev_map - noise_map
            elif mode == 'multiply':
                amp = params["amp_m"]
                if amp > 1e-9:
                    scale = (noise_map / amp) + 1.0
                else:
                    scale = np.ones_like(noise_map, dtype=float)
                final_map = prev_map * scale
            else:
                final_map = prev_map + noise_map  # безопасный дефолт

        self._result_cache = final_map
        return self._result_cache

    # ---------------------------- ВСПОМОГАТЕЛЬНОЕ ----------------------------

    def _make_internal_warp(self, ctx) -> tuple[np.ndarray | None, np.ndarray | None]:
        """
        Генерирует внутренние warp_x/warp_z по параметрам вкладки [Warp].
        """
        base = {
            "scale_tiles": self._as_float('warp_scale_tiles', 4000.0, pos=True),
            "octaves":     self._as_int('warp_octaves', 2, min_value=1),
            "ridge":       bool(self.get_property('warp_ridge')),
            "additive_only": False,
        }
        p_x = dict(base)
        p_z = dict(base)

        p_x["amp_m"] = self._as_float('warp_amp_x', 200.0, nonneg=True)
        p_z["amp_m"] = self._as_float('warp_amp_z', 200.0, nonneg=True)

        # разные сиды для независимости направлений
        p_x["seed_offset"] = 100
        p_z["seed_offset"] = 101

        wx = _generate_noise_field(p_x, ctx)
        wz = _generate_noise_field(p_z, ctx)

        h, w = ctx['x_coords'].shape
        if not isinstance(wx, np.ndarray) or wx.shape != (h, w):
            wx = np.zeros((h, w), dtype=float)
        if not isinstance(wz, np.ndarray) or wz.shape != (h, w):
            wz = np.zeros((h, w), dtype=float)

        return wx, wz

