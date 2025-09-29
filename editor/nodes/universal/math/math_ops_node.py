# ==============================================================================
# MathOpsNode: ВЕРСИЯ 2.0 (РЕФАКТОРИНГ): Использует get_property из базового класса.
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

        # РЕФАКТОРИНГ: Указываем типы для авто-преобразования
        self.add_enum_input("operation", "Operation",
                            ["add","sub","mul","div","pow","min","max","abs","lerp"],
                            tab="Settings", default="add")
        self._prop_meta["const_b"] = {'type': 'float', 'label': "Constant B", 'tab': "Settings", 'group': "Settings"}
        self.add_text_input("const_b", "Constant B", tab="Settings", text="0.0")

        self._prop_meta["lerp_t"] = {'type': 'float', 'label': "Lerp t (0..1)", 'tab': "Settings", 'group': "Settings"}
        self.add_text_input("lerp_t",  "Lerp t (0..1)", tab="Settings", text="0.5")

        self.add_enum_input("space_policy", "Space Policy",
                            ["auto","as_norm","as_meters"],
                            tab="Spaces", default="auto")
        self._prop_meta["world_max_m"] = {'type': 'float', 'label': "World Max (m) fallback", 'tab': "Spaces", 'group': "Spaces"}
        self.add_text_input("world_max_m", "World Max (m) fallback", tab="Spaces", text="1000")

        self.add_checkbox("use_clamp", "Post-clamp", tab="Clamp", state=False)
        self._prop_meta["clamp_min"] = {'type': 'float', 'label': "Min", 'tab': "Clamp", 'group': "Clamp"}
        self.add_text_input("clamp_min", "Min", tab="Clamp", text="0.0")
        self._prop_meta["clamp_max"] = {'type': 'float', 'label': "Max", 'tab': "Clamp", 'group': "Clamp"}
        self.add_text_input("clamp_max", "Max", tab="Clamp", text="1.0")

        self.set_color(40, 60, 90)
        self.set_description(DESC)

    # РЕФАКТОРИНГ: Вспомогательные методы _f и _enumv больше не нужны

    def _read_port(self, idx: int, context):
        p = self.get_input(idx)
        if p and p.connected_ports():
            return p.connected_ports()[0].node().compute(context)
        return None

    def _as_norm01(self, obj, context, fallback_ref=None) -> np.ndarray:
        if obj is None: return None
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
        if obj is None: return None
        try:
            return to_meters(obj, fallback_ref_m=fallback_ref)
        except Exception:
            a = get_data(obj)
            if isinstance(a, np.ndarray):
                return a.astype(np.float32, copy=False)
            return None

    def _compute(self, context):
        A_obj = self._read_port(0, context)
        if A_obj is None:
            zeros = np.zeros_like(context["x_coords"], dtype=np.float32)
            self._result_cache = zeros
            return zeros

        B_obj = self._read_port(1, context)
        A_space = get_space(A_obj, default=SPACE_NORM)
        A_arr   = get_data(A_obj)
        if not isinstance(A_arr, np.ndarray) or A_arr.ndim != 2:
            logger.error("MathOps: вход A некорректен, отдаю нули.")
            zeros = np.zeros_like(context["x_coords"], dtype=np.float32)
            self._result_cache = zeros
            return zeros
        H, W = A_arr.shape

        # РЕФАКТОРИНГ: Прямое использование get_property()
        policy = self.get_property("space_policy")
        const_b = self.get_property("const_b")
        world_max = float(context.get("world_max_height_m", self.get_property("world_max_m")))

        if policy == "as_norm":
            A = self._as_norm01(A_obj, context, fallback_ref=world_max)
            B = self._as_norm01(B_obj, context, fallback_ref=world_max) if B_obj is not None else np.full((H, W), const_b, dtype=np.float32)
            out_space = SPACE_NORM
        elif policy == "as_meters":
            A = self._as_meters(A_obj, context, fallback_ref=world_max)
            B = self._as_meters(B_obj, context, fallback_ref=world_max) if B_obj is not None else np.full((H, W), const_b, dtype=np.float32)
            out_space = SPACE_METR
        else:  # auto
            if A_space == SPACE_METR:
                A = self._as_meters(A_obj, context, fallback_ref=world_max)
                B = self._as_meters(B_obj, context, fallback_ref=world_max) if B_obj is not None else np.full((H, W), const_b, dtype=np.float32)
                out_space = SPACE_METR
            else:
                A = self._as_norm01(A_obj, context, fallback_ref=world_max)
                B = self._as_norm01(B_obj, context, fallback_ref=world_max) if B_obj is not None else np.full((H, W), const_b, dtype=np.float32)
                out_space = SPACE_NORM

        if A is None or (B is None and self.get_input(1) and self.get_input(1).connected_ports()):
            logger.error("MathOps: не удалось привести входы к выбранному пространству.")
            zeros = np.zeros_like(A_arr, dtype=np.float32)
            self._result_cache = zeros if out_space == SPACE_NORM else make_packet(zeros, out_space, ref_m=world_max)
            return self._result_cache

        A = A.astype(np.float32, copy=False)
        if isinstance(B, np.ndarray):
            B = B.astype(np.float32, copy=False)

        op = self.get_property("operation")
        if op == "add": R = A + B
        elif op == "sub": R = A - B
        elif op == "mul": R = A * B
        elif op == "div": R = A / (B + 1e-8)
        elif op == "pow": R = np.power(A, B)
        elif op == "min": R = np.minimum(A, B)
        elif op == "max": R = np.maximum(A, B)
        elif op == "abs": R = np.abs(A)
        else:  # lerp
            t = float(np.clip(self.get_property("lerp_t"), 0.0, 1.0))
            R = A * (1.0 - t) + (B if isinstance(B, np.ndarray) else float(B)) * t

        if self.get_property("use_clamp"):
            cmin = self.get_property("clamp_min")
            cmax = self.get_property("clamp_max")
            if out_space == SPACE_NORM:
                cmin = float(np.clip(cmin, 0.0, 1.0))
                cmax = float(np.clip(cmax, 0.0, 1.0))
            if cmax < cmin: cmin, cmax = cmax, cmin
            np.clip(R, cmin, cmax, out=R)

        if get_space(A_obj, default=None) in (SPACE_NORM, SPACE_METR):
            pkt = make_packet(R.astype(np.float32, copy=False), space=out_space, ref_m=world_max if out_space == SPACE_METR else 1.0)
            self._result_cache = pkt
        else:
            self._result_cache = R.astype(np.float32, copy=False)

        return self._result_cache
