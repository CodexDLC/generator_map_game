# editor/nodes/height/composition/combiner_node.py
# ВЕРСИЯ 2.0 (ТВОРЧЕСКИЙ РЕФАКТОРИНГ): Нода теперь работает только в пространстве [0..1].
from __future__ import annotations
import logging
import numpy as np

from editor.nodes.base_node import GeneratorNode
# --- ИЗМЕНЕНИЕ: Упрощаем импорты, пакеты больше не нужны --- 
from game_engine_restructured.numerics.field_packet import get_data

# Импорт новой бизнес-логики
from generator_logic.core.composition import combine
from generator_logic.core.postprocessing import apply_clamp, apply_extend
from generator_logic.core.enhance import apply_autolevel

logger = logging.getLogger(__name__)

class CombinerNode(GeneratorNode):
    __identifier__ = "Ландшафт.Композиция"
    NODE_NAME = "Combiner"

    def __init__(self):
        super().__init__()
        self.add_input("A")
        self.add_input("B")
        self.add_output("Out")

        # --- Новая структура UI ---
        self.add_enum_input("operation", "Mode",
                            ["Add", "Subtract", "Multiply", "Divide", "Min", "Max", "Lerp",
                             "Screen", "Overlay", "Difference", "Dodge", "Burn",
                             "Soft Light", "Hard Light", "Hypotenuse"],
                            tab="Params", group="Settings", default="Add")
        self.add_text_input("const_b", "Constant B", tab="Params", group="Settings", text="0.0")
        self.add_text_input("lerp_t", "Ratio (0..1)", tab="Params", group="Settings", text="0.5")

        self.add_float_input("lerp_t", "Ratio (0..1)", value=0.5, tab="Params", group="Settings")

        self.add_enum_input("output_mode", "Output", ["None", "Clamp", "Extend"],
                            tab="Params", group="Output", default="None")

        self.add_enum_input("enhance_mode", "Enhance", ["None", "Autolevel"],
                            tab="Params", group="Enhance", default="None")

        # --- ИЗМЕНЕНИЕ: Группа "Spaces" полностью удалена ---

        self.set_color(40, 60, 90)
        self.set_description("Комбинирует два слоя (A и B) с помощью различных математических операций.")

    def _read_port(self, idx: int, context):
        p = self.get_input(idx)
        if p and p.connected_ports():
            return p.connected_ports()[0].node().compute(context)
        return None

    # --- ИЗМЕНЕНИЕ: Полностью переписанный и упрощенный метод вычисления ---
    def _compute(self, context):
        A_obj = self._read_port(0, context)
        if A_obj is None:
            # Если входа А нет, возвращаем пустой результат 0..1
            return np.zeros_like(context["x_coords"], dtype=np.float32)

        B_obj = self._read_port(1, context)

        # Всегда работаем с данными как с простыми массивами [0..1]
        A = get_data(A_obj)
        B = get_data(B_obj) if B_obj is not None else np.full_like(A, self.get_property("const_b"), dtype=np.float32)

        # 1. Основная операция
        R = combine(A, B, mode=self.get_property("operation"), ratio=self.get_property("lerp_t"))

        # 2. Постобработка
        output_mode = self.get_property("output_mode")
        if output_mode == "Clamp":
            R = apply_clamp(R, 0.0, 1.0) # Всегда зажимаем в [0,1]
        elif output_mode == "Extend":
            R = apply_extend(R)

        # 3. Улучшение
        enhance_mode = self.get_property("enhance_mode")
        if enhance_mode == "Autolevel":
            R = apply_autolevel(R)

        # Результат - всегда простой массив NumPy. Пакет больше не нужен.
        self._result_cache = R.astype(np.float32)
        return self._result_cache
