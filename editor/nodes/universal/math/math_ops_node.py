# ==============================================================================
# MathOpsNode: универсальные матоперации для полей (packet или ndarray).
# Поддержка пространств: norm01 ↔ meters (авто-конверт B под A).
# Входы:
#   A : packet|ndarray
#   B : packet|ndarray (опционально) или константа 'const_b'
# Выход:
#   Out : packet того же space, что и у A (если A - packet), иначе ndarray float32
# ==============================================================================

from __future__ import annotations
import logging
import numpy as np

from editor.nodes.base_node import GeneratorNode
from game_engine_restructured.numerics.field_packet import (
    make_packet, get_data, get_space, to_meters, to_norm01,
    SPACE_NORM, SPACE_METR
)

logger = logging.getLogger(__name__)

IDENT = "Универсальные.Математика"
NAME  = "Math Ops"

DESC = """
Универсальные матоперации над полями. Поддерживает packet/ndarray.
Space policy:
  - auto     : B приводится к пространству A автоматически (norm01<->meters)
  - as_norm  : оба операнда приводятся к norm01
  - as_meters: оба операнда приводятся к meters (требует ref у нормали)
Пост-кламп: опционально ограничивает результат (в текущем space).
"""

class MathOpsNode(GeneratorNode):
    __identifier__ = IDENT
    NODE_NAME = NAME

    def __init__(self):
        super().__init__()
        self.add_input("A")
        self.add_input("B")
        self.add_output("Out")

        # операции
        self.add_enum_input("operation", "Operation",
                            ["add","sub","mul","div","pow","min","max","abs","lerp"],
                            tab="Settings", default="add")
        self.add_text_input("const_b", "Constant B", tab="Settings", text="0.0")
        self.add_text_input("lerp_t",  "Lerp t (0..1)", tab="Settings", text="0.5")

        # политика пространств
        self.add_enum_input("space_policy", "Space Policy",
                            ["auto","as_norm","as_meters"],
                            tab="Spaces", default="auto")
        self.add_text_input("world_max_m", "World Max (m) fallback", tab="Spaces", text="1000")

        # пост-кламп
        self.add_checkbox("use_clamp", "Post-clamp", tab="Clamp", state=False)
        self.add_text_input("clamp_min", "Min", tab="Clamp", text="0.0")
        self.add_text_input("clamp_max", "Max", tab="Clamp", text="1.0")

        self.set_color(40, 60, 90)
        self.set_description(DESC)

    # ---------- helpers ----------
    def _f(self, name: str, default: float) -> float:
        v = self.get_property(name)
        try:
            if v in ("", None): return float(default)
            x = float(v)
            return x if np.isfinite(x) else float(default)
        except Exception:
            return float(default)

    def _enumv(self, name: str, allowed: list[str], default: str) -> str:
        return self._enum(name, allowed, default)

    def _read_port(self, idx: int, context):
        p = self.get_input(idx)
        if p and p.connected_ports():
            return p.connected_ports()[0].node().compute(context)
        return None

    def _as_norm01(self, obj, context, fallback_ref=None) -> np.ndarray:
        """ obj (packet|ndarray) -> ndarray [0..1] """
        if obj is None:
            return None
        try:
            return to_norm01(obj, fallback_ref=fallback_ref, clip=True)
        except Exception:
            a = get_data(obj)
            if isinstance(a, np.ndarray):
                a = a.astype(np.float32, copy=False)
                np.clip(a, 0.0, 1.0, out=a)
                return a
            return None

    def _as_meters(self, obj, context, fallback_ref=None) -> np.ndarray:
        """ obj (packet|ndarray) -> ndarray meters """
        if obj is None:
            return None
        try:
            return to_meters(obj, fallback_ref_m=fallback_ref)
        except Exception:
            a = get_data(obj)
            if isinstance(a, np.ndarray):
                # считаем что уже метры
                return a.astype(np.float32, copy=False)
            return None

    # ---------- compute ----------
    def _compute(self, context):
        A_obj = self._read_port(0, context)
        if A_obj is None:
            zeros = np.zeros_like(context["x_coords"], dtype=np.float32)
            self._result_cache = zeros
            return zeros

        B_obj = self._read_port(1, context)

        # определить space/shape по A
        A_space = get_space(A_obj, default=SPACE_NORM)
        A_arr   = get_data(A_obj)
        if not isinstance(A_arr, np.ndarray) or A_arr.ndim != 2:
            logger.error("MathOps: вход A некорректен, отдаю нули.")
            zeros = np.zeros_like(context["x_coords"], dtype=np.float32)
            self._result_cache = zeros
            return zeros
        H, W = A_arr.shape

        # читаем политику пространств
        policy = self._enumv("space_policy", ["auto","as_norm","as_meters"], "auto")
        world_max = float(context.get("world_max_height_m",
                           self._f("world_max_m", 1000.0)))

        # подготовим A,B к общей системе единиц
        if policy == "as_norm":
            A = self._as_norm01(A_obj, context, fallback_ref=world_max)
            if B_obj is None:
                B = np.full((H, W), self._f("const_b", 0.0), dtype=np.float32)
            else:
                B = self._as_norm01(B_obj, context, fallback_ref=world_max)
            out_space = SPACE_NORM

        elif policy == "as_meters":
            A = self._as_meters(A_obj, context, fallback_ref=world_max)
            if B_obj is None:
                B = np.full((H, W), self._f("const_b", 0.0), dtype=np.float32)
            else:
                B = self._as_meters(B_obj, context, fallback_ref=world_max)
            out_space = SPACE_METR

        else:  # auto
            if A_space == SPACE_METR:
                A = self._as_meters(A_obj, context, fallback_ref=world_max)
                if B_obj is None:
                    B = np.full((H, W), self._f("const_b", 0.0), dtype=np.float32)
                else:
                    # приводим B к метрам
                    B = self._as_meters(B_obj, context, fallback_ref=world_max)
                out_space = SPACE_METR
            else:
                # трактуем как norm01
                A = self._as_norm01(A_obj, context, fallback_ref=world_max)
                if B_obj is None:
                    B = np.full((H, W), self._f("const_b", 0.0), dtype=np.float32)
                else:
                    B = self._as_norm01(B_obj, context, fallback_ref=world_max)
                out_space = SPACE_NORM

        if A is None or (B is None and self.get_input(1) and self.get_input(1).connected_ports()):
            logger.error("MathOps: не удалось привести входы к выбранному пространству.")
            zeros = np.zeros_like(A_arr, dtype=np.float32)
            self._result_cache = zeros if out_space == SPACE_NORM else make_packet(zeros, out_space, ref_m=world_max)
            return self._result_cache

        A = A.astype(np.float32, copy=False)
        if isinstance(B, np.ndarray):
            B = B.astype(np.float32, copy=False)

        # операция
        op = self._enumv("operation", ["add","sub","mul","div","pow","min","max","abs","lerp"], "add")
        if op == "add":
            R = A + B
        elif op == "sub":
            R = A - B
        elif op == "mul":
            R = A * B
        elif op == "div":
            eps = 1e-8
            R = A / (B + eps)
        elif op == "pow":
            # безопасная степень: отрицательные базы позволяем только для целых экспонент
            if isinstance(B, np.ndarray):
                Bi = np.rint(B)
                same = np.allclose(B, Bi, atol=1e-6)
                base = np.clip(A, 0.0, None) if (not same) and (out_space == SPACE_NORM) else A
                R = np.power(base, B)
            else:
                # B скаляр
                if (B % 1.0) != 0.0 and out_space == SPACE_METR:
                    base = np.clip(A, 0.0, None)
                else:
                    base = A
                R = np.power(base, B)
        elif op == "min":
            R = np.minimum(A, B)
        elif op == "max":
            R = np.maximum(A, B)
        elif op == "abs":
            R = np.abs(A)
        else:  # lerp
            t = float(np.clip(self._f("lerp_t", 0.5), 0.0, 1.0))
            R = A * (1.0 - t) + (B if isinstance(B, np.ndarray) else float(B)) * t

        # пост-кламп (в текущем space)
        if bool(self.get_property("use_clamp")):
            cmin = self._f("clamp_min", 0.0)
            cmax = self._f("clamp_max", 1.0)
            if out_space == SPACE_NORM:
                cmin = float(np.clip(cmin, 0.0, 1.0))
                cmax = float(np.clip(cmax, 0.0, 1.0))
            if cmax < cmin:
                cmin, cmax = cmax, cmin
            np.clip(R, cmin, cmax, out=R)

        # упаковка результата
        if get_space(A_obj, default=None) in (SPACE_NORM, SPACE_METR):
            # если A был packet — возвращаем packet в его space
            if out_space == SPACE_NORM:
                pkt = make_packet(R.astype(np.float32, copy=False), space=SPACE_NORM, ref_m=1.0)
            else:
                pkt = make_packet(R.astype(np.float32, copy=False), space=SPACE_METR, ref_m=world_max)
            self._result_cache = pkt
        else:
            # иначе — просто массив
            self._result_cache = R.astype(np.float32, copy=False)

        return self._result_cache
