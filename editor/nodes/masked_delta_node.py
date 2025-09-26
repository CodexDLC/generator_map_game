# ==============================================================================
# Файл: editor/nodes/masked_delta_node.py
# Роль: Формирует Δвысоты (м) по маскам. На входе карта-источник и одна/несколько масок,
#       на выходе — уже умноженная дельта в метрах, которую можно складывать в поток.
# ==============================================================================
from __future__ import annotations
import numpy as np
from editor.nodes.base_node import GeneratorNode


class MaskedDeltaNode(GeneratorNode):
    """
    Категория: Ландшафт.Композиция
    Роль: Сформировать «дельту высоты» в метрах на основе источника и масок.

    Входы:
      0) Source    — карта-источник (либо метры, либо unit01)
      1) Mask(s)   — одна или несколько масок 0..1

    Выход:
      - Delta (m)  — дельта высоты в метрах (готова к сложению)

    Параметры:
      [Source]
        - Source Type: meters | unit01
          meters:     считаем, что источник уже в метрах → Δ = source * M
          unit01:     считаем, что источник в [0..1]; пересчёт:
                        src01_centered = (source - 0.5) * 2    # [-1..1]
                        Δ = src01_centered * Scale(m) * M
        - Scale (m): множитель для режима unit01 (по умолчанию 100)

      [Masks]
        - Combine:  max | multiply
          max      : объединение масок как максимум (логическое ИЛИ)
          multiply : поэлементное произведение (логическое И)
        - Invert: инвертировать итоговую маску (1 - M)
    """

    __identifier__ = "Ландшафт.Композиция"
    NODE_NAME = "Masked Delta"

    def __init__(self):
        super().__init__()

        src = self.add_input("Source", "Source")
        msk = self.add_input("Mask(s)", "Mask")
        self.add_output("Delta (m)", "Out")

        # Маски и источник разрешаем подключать множественно
        for p in (src, msk):
            try:
                if hasattr(p, "set_multi_connections"):
                    p.set_multi_connections(True)
                elif hasattr(p, "set_multi_connection"):
                    p.set_multi_connection(True)
            except Exception:
                pass

        # Параметры
        self.add_combo_menu("source_type", "Source Type",
                            items=["meters", "unit01"], tab="Source")
        self.add_text_input("scale_m", "Scale (m)", tab="Source", text="100")

        self.add_combo_menu("mask_combine", "Combine",
                            items=["max", "multiply"], tab="Masks")
        self.add_checkbox("invert_mask", "Invert", tab="Masks", state=False)

        self.set_color(90, 70, 25)
        self.set_description("""
        Делает дельту высоты по маскам. Если источник уже в метрах — просто умножает
        на итоговую маску. Если источник в [0..1] — центрирует его вокруг 0 и
        масштабирует по параметру Scale (м), затем умножает на маску.
        """)

    # ---------------- helpers ----------------

    def _as_float(self, name: str, default: float) -> float:
        v = self.get_property(name)
        try:
            x = float(v)
            if not np.isfinite(x):
                return default
            return x
        except Exception:
            return default

    def _gather_sources_sum(self, port, context) -> np.ndarray | None:
        """Складывает все подключенные карты-источники (если несколько)."""
        if not port:
            return None
        conns = port.connected_ports() or []
        if not conns:
            return None
        shape = context["x_coords"].shape
        acc = np.zeros(shape, dtype=float)
        have_any = False
        for p in conns:
            try:
                m = p.node().compute(context)
                if isinstance(m, np.ndarray) and m.shape == shape:
                    acc += m
                    have_any = True
            except Exception:
                pass
        return acc if have_any else None

    def _gather_mask(self, port, context) -> np.ndarray:
        """Комбинирует маски по правилу max или multiply."""
        shape = context["x_coords"].shape
        if not port:
            return np.ones(shape, dtype=float)
        conns = port.connected_ports() or []
        if not conns:
            return np.ones(shape, dtype=float)

        combine = (self.get_property("mask_combine") or "max").lower()
        if combine not in ("max", "multiply"):
            combine = "max"

        if combine == "max":
            acc = np.zeros(shape, dtype=float)
            for p in conns:
                try:
                    m = p.node().compute(context)
                    if isinstance(m, np.ndarray) and m.shape == shape:
                        acc = np.maximum(acc, np.clip(m, 0.0, 1.0))
                except Exception:
                    pass
        else:  # multiply
            acc = np.ones(shape, dtype=float)
            for p in conns:
                try:
                    m = p.node().compute(context)
                    if isinstance(m, np.ndarray) and m.shape == shape:
                        acc *= np.clip(m, 0.0, 1.0)
                except Exception:
                    pass

        if bool(self.get_property("invert_mask")):
            acc = 1.0 - acc
        return acc

    # ---------------- compute ----------------

    def compute(self, context):
        shape = context["x_coords"].shape

        src_map = self._gather_sources_sum(self.get_input(0), context)
        if src_map is None:
            # Нет источника — дельта нулевая
            self._result_cache = np.zeros(shape, dtype=float)
            return self._result_cache

        M = self._gather_mask(self.get_input(1), context)

        stype = (self.get_property("source_type") or "meters").lower()
        if stype == "unit01":
            scale = self._as_float("scale_m", 100.0)
            centered = (src_map - 0.5) * 2.0       # [-1..1]
            delta = centered * scale * M
        else:  # meters
            delta = src_map * M

        self._result_cache = delta.astype(float, copy=False)
        return self._result_cache
