# ==============================================================================
# DomainWarpApply: внешнее доменное искажение для ЛЮБОГО источника.
# Входы:
#   - src     : узел-источник (любой), который читает context["x_coords"/"z_coords"]
#   - warp_x  : шум/карта, задающая смещение по X
#   - warp_z  : шум/карта, задающая смещение по Z (если не подключен — берём warp_x)
#
# Свойства:
#   - amp_x_m   : амплитуда смещения по X (м), применяется если warp_* в нормали
#   - amp_z_m   : амплитуда смещения по Z (м), применяется если warp_* в нормали
#   - strength  : общий множитель [0..1]
#   - warp_mode : enum("auto","norm","meters")
#       auto   — если warp_* = norm01 → [-1..1]*amp; если meters → используем как есть
#       norm   — трактуем warp_* как norm01 независимо от packet.space
#       meters — трактуем warp_* как метры независимо от packet.space
#
# Выход:
#   - out: результат src, пересчитанный в новых координатах (тип не меняется)
# ==============================================================================

from __future__ import annotations
import logging
import numpy as np
from editor.nodes.base_node import GeneratorNode
from game_engine_restructured.numerics.field_packet import (
    get_data, get_space, SPACE_NORM, SPACE_METR
)

logger = logging.getLogger(__name__)

IDENT = "Универсальные.Модули"
NAME  = "Domain Warp (Apply)"

DESC = """
Внешний доменный варп: берёт 'src' и смещает его координаты по полям 'warp_x'/'warp_z'.
warp_* можно подавать как нормаль [0..1] (тогда масштабируется амплитудами в метрах),
или как метры (используются напрямую). Режим выбирается параметром warp_mode.
"""

class DomainWarpApplyNode(GeneratorNode):
    __identifier__ = IDENT
    NODE_NAME = NAME

    def __init__(self):
        super().__init__()
        # основной горизонтальный поток
        self.add_input("src")
        self.add_output("out")
        # вертикальные "ответвления" (на UI можно разместить сверху/снизу)
        self.add_input("warp_x")
        self.add_input("warp_z")

        # параметры
        self.add_text_input("amp_x_m",   "Amplitude X (m)", tab="Warp", text="200")
        self.add_text_input("amp_z_m",   "Amplitude Z (m)", tab="Warp", text="200")
        # enum-хелпер из базового класса: если нет combo, будет валидированный текст
        self.add_enum_input("warp_mode", "Warp Mode", ["auto","norm","meters"], tab="Warp", default="auto")
        self.add_text_input("strength",  "Strength (0..1)", tab="Warp", text="1.0")

        self.set_color(40, 90, 90)
        self.set_description(DESC)

    # ------------- helpers -------------

    def _f(self, name: str, default: float) -> float:
        v = self.get_property(name)
        try:
            if v in ("", None): return float(default)
            x = float(v);
            return x if np.isfinite(x) else float(default)
        except Exception:
            return float(default)

    def _amp(self, name: str, default: float) -> float:
        return max(0.0, self._f(name, default))

    def _read_src(self, port_name: str, context):
        p = self.get_input(port_name)
        if not (p and p.connected_ports()):
            return None
        return p.connected_ports()[0].node().compute(context)

    def _as_warp_meters(self, obj, amp_m: float, mode: str, fallback_shape) -> np.ndarray:
        """
        Преобразует вход (packet или ndarray) в смещение в МЕТРАХ.
        mode: "auto"|"norm"|"meters"
        """
        arr = get_data(obj) if obj is not None else None
        if not isinstance(arr, np.ndarray) or arr.ndim != 2:
            return np.zeros(fallback_shape, dtype=np.float32)

        sp  = get_space(obj, default=SPACE_NORM) if obj is not None else SPACE_NORM

        if mode == "meters":
            # трактуем как метры без изменений
            return arr.astype(np.float32, copy=False)

        if mode == "norm" or (mode == "auto" and sp == SPACE_NORM):
            # нормаль [0..1] → [-1..1] → метры через амплитуду
            a = arr.astype(np.float32, copy=False)
            np.clip(a, 0.0, 1.0, out=a)
            return (a * 2.0 - 1.0) * float(amp_m)

        # auto + (sp == SPACE_METR):
        return arr.astype(np.float32, copy=False)

    # ------------- core -------------

    def _compute(self, context):
        # 0) обязательный источник
        src = self._read_src("src", context)
        if src is None:
            logger.error("DomainWarpApply: вход 'src' не подключён — возвращаю нули.")
            zeros = np.zeros_like(context["x_coords"], dtype=np.float32)
            self._result_cache = zeros
            return zeros

        # 1) читаем warp_*; если z нет — используем x
        wx_obj = self._read_src("warp_x", context)
        wz_obj = self._read_src("warp_z", context) or wx_obj

        xc = context.get("x_coords"); zc = context.get("z_coords")
        if not (isinstance(xc, np.ndarray) and isinstance(zc, np.ndarray) and xc.shape == zc.shape):
            logger.error("DomainWarpApply: некорректные координаты в контексте.")
            self._result_cache = src
            return src

        # 2) конвертируем warp в метры
        mode = self._enum("warp_mode", ["auto","norm","meters"], "auto")
        wx_m = self._as_warp_meters(wx_obj, self._amp("amp_x_m", 200.0), mode, xc.shape)
        wz_m = self._as_warp_meters(wz_obj, self._amp("amp_z_m", 200.0), mode, xc.shape)

        # форма защита
        if wx_m.shape != xc.shape or wz_m.shape != xc.shape:
            logger.error("DomainWarpApply: несовпадение форм warp и координат — пробрасываю src без варпа.")
            self._result_cache = src
            return src

        # 3) сила
        s = float(np.clip(self._f("strength", 1.0), 0.0, 1.0))
        if s <= 1e-6 or (np.max(np.abs(wx_m)) < 1e-12 and np.max(np.abs(wz_m)) < 1e-12):
            # нет смысла варпить
            self._result_cache = src
            return src

        # 4) локальный контекст со смещёнными координатами
        local_ctx = dict(context)
        local_ctx["_ctx_rev"] = int(context.get("_ctx_rev", 0)) + 1  # заставим источник пересчитаться
        local_ctx["x_coords"] = xc + wx_m * s
        local_ctx["z_coords"] = zc + wz_m * s

        # 5) пересчитываем src в новых координатах; тип выходим ровно тот же
        res = self.get_input("src").connected_ports()[0].node().compute(local_ctx)
        self._result_cache = res
        return res
