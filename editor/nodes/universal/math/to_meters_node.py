# ==============================================================================
# Файл: editor/nodes/universal/math/to_meters_node.py
# Назначение: Конвертация шума [0..1] в метры + прикрепление пакета метаданных.
# ==============================================================================

from __future__ import annotations
import numpy as np
from editor.nodes.base_node import GeneratorNode
from game_engine_restructured.numerics.field_packet import (
    make_packet, is_packet, get_data, get_space, get_ref_m,
    SPACE_NORM, SPACE_METR
)

# --- Локализация/лейблы ---
IDENTIFIER_LBL   = "Универсальные.Математика"
NODE_NAME_LBL    = "To Meters"
DESCRIPTION_TEXT = (
    "Переводит входной шум в метры и прикрепляет метаданные пакета:\n"
    "  - space='meters', amp_m, bias_m, ref_m (по policy)\n"
    "Если вход уже в метрах — не масштабирует (применит только Offset)."
)

TAB_MAIN   = "Main"
L_AMP      = "Amplitude (m)"
L_OFFSET   = "Offset (m)"
L_POLICY   = "Ref Policy (amp|world|none)"
L_WMAX     = "World Max (m) fallback"

class ToMetersNode(GeneratorNode):
    __identifier__ = IDENTIFIER_LBL
    NODE_NAME = NODE_NAME_LBL

    def __init__(self):
        super().__init__()
        self.add_input('height')   # может прийти ndarray или пакет
        self.add_output('height')  # отдаём ПАКЕТ (dict) в space="meters"

        self.add_text_input('amp_m',    L_AMP,    tab=TAB_MAIN, text="200")
        self.add_text_input('offset_m', L_OFFSET, tab=TAB_MAIN, text="0")
        self.add_enum_input('ref_policy', L_POLICY, ["amp", "world", "none"], tab=TAB_MAIN, default="amp")
        self.add_text_input('world_max_m', L_WMAX, tab=TAB_MAIN, text="1000")

        self.set_color(30, 70, 30)
        self.set_description(DESCRIPTION_TEXT)

    def _f(self, name, default):
        v = self.get_property(name)
        try:
            if v in ("", None):
                return float(default)
            return float(v)
        except (TypeError, ValueError):
            return float(default)

    def _compute(self, context):
        port = self.get_input('height')
        if not (port and port.connected_ports()):
            # отдаём пустой пакет (ноль метров), чтобы потребители не падали
            empty = np.zeros_like(context["x_coords"], dtype=np.float32)
            pkt = make_packet(empty, space=SPACE_METR, ref_m=None, amp_m=None, bias_m=0.0)
            self._result_cache = pkt
            return pkt

        src = port.connected_ports()[0].node().compute(context)
        space = get_space(src)
        amp   = self._f('amp_m', 200.0)
        offs  = self._f('offset_m', 0.0)

        # 1) Преобразование в метры
        X = get_data(src)
        if space == SPACE_NORM:
            # нормаль -> метры
            data_m = X * amp + offs
            amp_out = amp
        else:
            # уже метры — уважаем вход и только добавляем offset
            data_m = X + offs
            # Если входной пакет знал амплитуду — сохраним, иначе None
            try:
                from game_engine_restructured.numerics.field_packet import get_amp_m
                amp_in = get_amp_m(src, None)
            except Exception:
                amp_in = None
            amp_out = amp_in

        # 2) Выбор ref_m по policy
        policy = self._enum('ref_policy', ["amp", "world", "none"], "amp")
        world_max = None
        try:
            world_max = context.get("height_max_m") or (context.get("project") or {}).get("height_max_m")
        except Exception:
            world_max = None
        if world_max is None:
            world_max = self._f('world_max_m', 1000.0)

        if policy == "world":
            ref_m = float(world_max)
        elif policy == "amp":
            ref_m = float(amp_out) if amp_out is not None else float(amp)
        elif policy == "none":
            ref_m = None
        else:
            # неизвестная политика -> безопасно как 'amp'
            ref_m = float(amp_out) if amp_out is not None else float(amp)

        pkt = make_packet(data_m, space=SPACE_METR, ref_m=ref_m, amp_m=amp_out, bias_m=offs)
        self._result_cache = pkt
        return pkt
