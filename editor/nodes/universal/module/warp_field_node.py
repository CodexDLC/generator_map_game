# ==============================================================================
# WarpFieldNode: генерит поле смещений координат (warp_x, warp_z) в МЕТРАХ.
# Входы (опц.): noise_x, noise_z  — packet/ndarray; трактуются как нормаль [0..1]
#               (или метры — переключается режимом), конвертируются в метры.
# Если вход не подключён — используем внутренний FBM.
# Выходы: warp_x (m), warp_z (m) — ndarray float32, shape как у x_coords.
# ==============================================================================

from __future__ import annotations
import logging
import numpy as np

from editor.nodes.base_node import GeneratorNode
from game_engine_restructured.algorithms.terrain.steps.noise import _generate_noise_field
from game_engine_restructured.numerics.field_packet import (
    get_data, get_space, SPACE_NORM, SPACE_METR
)

logger = logging.getLogger(__name__)

IDENT = "Универсальные.Модули"
NAME  = "Warp Field"

DESC = """
Создаёт поле смещений координат в метрах: warp_x, warp_z.
Если подключены noise_x/noise_z — они переводятся в метры по амплитудам (или берутся как метры).
Если не подключены — используется внутренний FBM (нормаль → [-1..1] → метры).
Подключай выходы к DomainWarp(Apply)."""

class WarpFieldNode(GeneratorNode):
    __identifier__ = IDENT
    NODE_NAME = NAME

    def __init__(self):
        super().__init__()
        # входы-ответвления (вертикально): можно подать свои шумы
        self.add_input("noise_x")
        self.add_input("noise_z")
        # выходы
        self.add_output("warp_x")
        self.add_output("warp_z")

        # как трактовать входные noise_*:
        self.add_enum_input("warp_mode", "Input Mode", ["auto","norm","meters"], tab="Warp", default="auto")
        # амплитуды (м) — применяются, когда noise_* трактуются как нормаль
        self.add_text_input("amp_x_m", "Amplitude X (m)", tab="Warp", text="200")
        self.add_text_input("amp_z_m", "Amplitude Z (m)", tab="Warp", text="200")

        # fallback FBM (если входов нет)
        self.add_text_input("scale_tiles", "FBM Scale (tiles)", tab="FBM Fallback", text="4000")
        self.add_text_input("octaves",     "FBM Octaves",       tab="FBM Fallback", text="2")
        self.add_checkbox   ("ridge",      "FBM Ridge",         tab="FBM Fallback", state=False)
        self.add_seed_input("seed_offset", "FBM Seed Offset",   tab="FBM Fallback")

        self.set_color(40, 90, 90)
        self.set_description(DESC)

    # ---------- helpers ----------
    def _f(self, name, default):
        v = self.get_property(name)
        try:
            if v in ("", None): return float(default)
            x = float(v)
            return x if np.isfinite(x) else float(default)
        except Exception:
            return float(default)

    def _i(self, name, default, mn=None):
        v = self.get_property(name)
        try:
            x = int(float(v))
            if mn is not None: x = max(x, mn)
            return x
        except Exception:
            return default

    def _read_port(self, name, context):
        p = self.get_input(name)
        if p and p.connected_ports():
            return p.connected_ports()[0].node().compute(context)
        return None

    def _to_warp_meters(self, obj, amp_m: float, mode: str, shape) -> np.ndarray:
        """packet/ndarray -> ndarray[float32] в метрах"""
        if obj is None:
            return None
        arr = get_data(obj)
        if not isinstance(arr, np.ndarray) or arr.ndim != 2:
            return None

        sp = get_space(obj, default=SPACE_NORM)

        if mode == "meters" or (mode == "auto" and sp == SPACE_METR):
            return arr.astype(np.float32, copy=False)

        # mode == "norm" или auto+norm: [0..1] → [-1..1] → метры
        a = arr.astype(np.float32, copy=False)
        np.clip(a, 0.0, 1.0, out=a)
        return (a * 2.0 - 1.0) * float(amp_m)

    # ---------- compute ----------
    def _compute(self, context):
        xg = context.get("x_coords"); zg = context.get("z_coords")
        if not (isinstance(xg, np.ndarray) and isinstance(zg, np.ndarray) and xg.shape == zg.shape):
            H, W = (256, 256)
            zeros = np.zeros((H, W), dtype=np.float32)
            self._result_cache = (zeros, zeros)  # двоичный выход
            return self._result_cache

        mode = self._enum("warp_mode", ["auto","norm","meters"], "auto")
        amp_x = max(0.0, self._f("amp_x_m", 200.0))
        amp_z = max(0.0, self._f("amp_z_m", 200.0))

        # 1) пытаемся взять warp из входов
        wx = self._to_warp_meters(self._read_port("noise_x", context), amp_x, mode, xg.shape)
        wz = self._to_warp_meters(self._read_port("noise_z", context), amp_z, mode, xg.shape)

        # 2) если вход не подключен — fallback FBM
        if wx is None or wz is None:
            base = {
                "scale_tiles": max(self._f("scale_tiles", 4000.0), 1e-6),
                "octaves":     self._i("octaves", 2, mn=1),
                "ridge":       bool(self.get_property("ridge")),
                "amp_m":       1.0,
                "additive_only": True,
            }
            so = self._i("seed_offset", 0)
            # независимые сиды по осям
            px = dict(base, seed_offset=so + 100)
            pz = dict(base, seed_offset=so + 101)

            nx = _generate_noise_field(px, context)  # [0..1]
            nz = _generate_noise_field(pz, context)  # [0..1]
            if not isinstance(nx, np.ndarray): nx = np.zeros_like(xg, dtype=np.float32)
            if not isinstance(nz, np.ndarray): nz = np.zeros_like(xg, dtype=np.float32)

            wx_fb = (np.clip(nx.astype(np.float32, copy=False), 0.0, 1.0) * 2.0 - 1.0) * amp_x
            wz_fb = (np.clip(nz.astype(np.float32, copy=False), 0.0, 1.0) * 2.0 - 1.0) * amp_z
            if wx is None: wx = wx_fb
            if wz is None: wz = wz_fb

        # форма защита
        if wx.shape != xg.shape or wz.shape != xg.shape:
            logger.error("WarpFieldNode: несовпадение форм, отдаю нули.")
            zeros = np.zeros_like(xg, dtype=np.float32)
            self._result_cache = (zeros, zeros)
            return self._result_cache

        wx = wx.astype(np.float32, copy=False)
        wz = wz.astype(np.float32, copy=False)

        # два выхода (по портам): сначала warp_x, затем warp_z
        # NodeGraphQt сам подхватит self._result_cache, но вернём кортеж
        self._result_cache = (wx, wz)
        return self._result_cache
