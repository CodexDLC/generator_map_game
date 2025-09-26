# ==============================================================================
# Файл: editor/nodes/height_merge_node.py
# Роль: Слить базовую высоту и несколько Δвысот (м). Без масок и прочей логики.
#       Используй после нескольких Masked Delta, чтобы вернуть их в основной поток.
# ==============================================================================
from __future__ import annotations
import numpy as np
from editor.nodes.base_node import GeneratorNode


class HeightMergeNode(GeneratorNode):
    """
    Категория: Ландшафт.Пайплайн
    Роль: Сложить базовую высоту и набор дельт.

    Входы:
      0) Base Height (м) — обязательный вход
      1) Delta(s) (м)    — одна или несколько дельт для сложения

    Выход:
      - Height Out (м)

    Параметры:
      [Merge]
        - Mode: add | replace
          add     : result = base + ΣΔ
          replace : result = ΣΔ  (игнорирует base)
    """

    __identifier__ = "Ландшафт.Пайплайн"
    NODE_NAME = "Height Merge"

    def __init__(self):
        super().__init__()
        base = self.add_input("Base Height", "Base")
        deltas = self.add_input("Delta(s) (m)", "Delta")
        self.add_output("Height Out", "Out")

        # Разрешим несколько дельт
        try:
            if hasattr(deltas, "set_multi_connections"):
                deltas.set_multi_connections(True)
            elif hasattr(deltas, "set_multi_connection"):
                deltas.set_multi_connection(True)
        except Exception:
            pass

        self.add_combo_menu("merge_mode", "Mode", items=["add", "replace"], tab="Merge")

        self.set_color(45, 95, 120)
        self.set_description("""
        Складывает базовую карту и набор дельт в метрах.
        В режиме 'replace' базовая высота игнорируется.
        """)

    def _sum_port(self, port, context) -> np.ndarray:
        shape = context["x_coords"].shape
        acc = np.zeros(shape, dtype=float)
        if not port:
            return acc
        for p in (port.connected_ports() or []):
            try:
                m = p.node().compute(context)
                if isinstance(m, np.ndarray) and m.shape == shape:
                    acc += m
            except Exception:
                pass
        return acc

    def compute(self, context):
        shape = context["x_coords"].shape

        # base (обязателен, но на всякий случай страхуемся)
        base_map = np.zeros(shape, dtype=float)
        p_base = self.get_input(0)
        if p_base and p_base.connected_ports():
            b = p_base.connected_ports()[0].node().compute(context)
            if isinstance(b, np.ndarray) and b.shape == shape:
                base_map = b

        deltas_sum = self._sum_port(self.get_input(1), context)

        mode = (self.get_property("merge_mode") or "add").lower()
        if mode == "replace":
            result = deltas_sum
        else:
            result = base_map + deltas_sum

        self._result_cache = result
        return self._result_cache
