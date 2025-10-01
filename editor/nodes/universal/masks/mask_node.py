# ==============================================================================
# Файл: editor/nodes/universal/masks/mask_node.py
# ВЕРСИЯ 1.0: Базовая нода маски по шуму или по высоте.
#   - Вход: height_in (packet или ndarray)
#   - Выход: mask (ndarray float32 в [0..1])
# ==============================================================================

from __future__ import annotations
import logging
import numpy as np
from editor.nodes.base_node import GeneratorNode
from game_engine_restructured.numerics.field_packet import (
    get_data, to_norm01
)

logger = logging.getLogger(__name__)

IDENTIFIER_LBL = "Универсальные.Маски"
NODE_NAME_LBL  = "Mask"

DESCRIPTION_TEXT = """
Создаёт маску из входной карты:
  mode=noise  — пороги заданы в нормали [0..1]
  mode=height — пороги заданы в метрах (делятся на ref)
  which=above | below — какую сторону порога брать
ref_policy (для mode=height):
  world — делить на world_max_height_m (из контекста или поля)
  layer — делить на ref_m входного пакета
Выход: ndarray float32, диапазон [0..1].
"""

class MaskNode(GeneratorNode):
    __identifier__ = IDENTIFIER_LBL
    NODE_NAME = NODE_NAME_LBL

    def __init__(self):
        super().__init__()
        self.add_input("height_in")
        self.add_output("mask")
        self.add_combo_menu("mode", "Mode", items=["noise", "height"], tab="Mask")
        self.add_combo_menu("which", "Which side", items=["above", "below"], tab="Mask")
        self.add_combo_menu("ref_policy", "Ref policy", items=["world", "layer"], tab="Mask")
        self.add_float_input("threshold", "Threshold (0..1)", tab="Mask", value=0.5)
        self.add_float_input("falloff", "Falloff width (0..1)", tab="Mask", value=0.1)
        self.add_text_input("world_max_m", "World Max (m) fallback", tab="Mask", text="1000")
        self.set_color(50, 50, 90)
        self.set_description(DESCRIPTION_TEXT)

        # — описание ноды (панель справа)
        self.set_description("""
        Маска из входной карты.
          • mode = noise  — пороги заданы в нормали [0..1].
          • mode = height — пороги заданы в метрах (преобразуются в нормаль по ref).
          • which: above (выше порога) или below (ниже порога).
          • threshold — сам порог (в [0..1] для noise, в метрах для height).
          • falloff — ширина плавного перехода вокруг порога
                      (в [0..1] при mode=noise, в метрах при mode=height).
          • ref_policy при mode=height:
              - world — делить пороги/градиент на world_max_height_m;
              - layer — делить на ref_m входного пакета (если есть).
          • world_max_m — запасной максимум мира на случай, если его нет в context.
        Выход: ndarray float32 в диапазоне [0..1].
        """.strip())

        # — подсказки (tooltips) на виджетах
        def tip(name, text):
            w = self.get_widget(name)
            if w and hasattr(w, "set_tooltip"):
                w.set_tooltip(text)

        tip("mode",
            "Режим порога:\n"
            " • noise — threshold/falloff заданы в [0..1]\n"
            " • height — threshold/falloff заданы в метрах"
            )
        tip("which",
            "Какую сторону порога сделать «белой»:\n"
            " • above — 0…1 растёт выше порога\n"
            " • below — 1…0 убывает выше порога"
            )
        tip("ref_policy",
            "Как переводить метры → нормаль (только при mode=height):\n"
            " • world — делить на world_max_height_m (из контекста)\n"
            " • layer — делить на ref_m входного пакета"
            )
        tip("threshold",
            "Порог срабатывания:\n"
            " • mode=noise: значение в [0..1]\n"
            " • mode=height: значение в метрах"
            )
        tip("falloff",
            "Ширина плавного перехода (границы smoothstep):\n"
            " • mode=noise: доля от диапазона [0..1]\n"
            " • mode=height: метры"
            )
        tip("world_max_m",
            "Запасной максимум мира (м), если в контексте нет world_max_height_m.\n"
            "Используется при mode=height и ref_policy=world."
            )

    # -------------------- helpers --------------------

    def _f(self, name: str, default: float) -> float:
        v = self.get_property(name)
        try:
            if v in ("", None):
                return float(default)
            return float(v)
        except (TypeError, ValueError):
            return float(default)

    @staticmethod
    def _clip01(x: np.ndarray) -> np.ndarray:
        np.clip(x, 0.0, 1.0, out=x)
        return x

    @staticmethod
    def _smoothstep(a: float, b: float, x: np.ndarray) -> np.ndarray:
        # 0 при x<=a, 1 при x>=b, плавный переход внутри (Кубический Херми́т)
        den = max(b - a, 1e-6)
        t = (x - a) / den
        np.clip(t, 0.0, 1.0, out=t)
        return t * t * (3.0 - 2.0 * t)

    # -------------------- core --------------------

    def _compute(self, context):
        # 1) вход
        port = self.get_input("height_in")
        if not (port and port.connected_ports()):
            logger.warning("MaskNode: вход не подключен, отдаю нули.")
            empty = np.zeros_like(context["x_coords"], dtype=np.float32)
            self._result_cache = empty
            return empty

        src = port.connected_ports()[0].node().compute(context)  # packet или ndarray
        arr = get_data(src)
        if not isinstance(arr, np.ndarray) or arr.ndim != 2:
            logger.error("MaskNode: вход некорректен, отдаю нули.")
            empty = np.zeros_like(context["x_coords"], dtype=np.float32)
            self._result_cache = empty
            return empty

        mode = self._enum("mode", ["noise", "height"], "noise")
        which = self._enum("which", ["above", "below"], "above")
        thr    = self._f("threshold", 0.5)
        fall   = self._f("falloff",   0.1)

        # 2) получаем высоту в нормали [0..1]
        height01: np.ndarray
        if mode == "height":
            policy = self._enum("ref_policy", ["world","layer"], "world")
            # выберем ref для нормализации метров
            if policy == "layer":
                # опираемся на ref_m входного пакета; если его нет — упадём в except
                try:
                    height01 = to_norm01(src, fallback_ref=None, clip=True)
                except Exception:
                    logger.error("MaskNode: нет ref_m в пакете при ref_policy=layer. Нули.")
                    empty = np.zeros_like(arr, dtype=np.float32)
                    self._result_cache = empty
                    return empty
                # Порог и falloff заданы в МЕТРАХ -> в нормаль поделив на тот же ref.
                # Поскольку to_norm01 использовал layer-ref, делим пороги на НЁМ:
                # К сожалению, без прямого доступа к ref здесь не узнать число.
                # Значит пороги преобразуем через world, если есть конфликт:
                world_max = float(context.get("world_max_height_m",
                                   (context.get("project") or {}).get("height_max_m", self._f("world_max_m", 1000.0))))
                # Предупреждение: если layer-ref != world_max, пороги будут относиться к world_max.
                thr_norm  = float(thr)  / world_max
                fall_norm = float(fall) / world_max
            else:
                # policy == "world"
                world_max = float(context.get("world_max_height_m",
                                   (context.get("project") or {}).get("height_max_m", self._f("world_max_m", 1000.0))))
                height01 = to_norm01(src, fallback_ref=world_max, clip=True)
                thr_norm  = float(thr)  / max(world_max, 1e-6)
                fall_norm = float(fall) / max(world_max, 1e-6)

            thr_norm  = float(np.clip(thr_norm,  0.0, 1.0))
            fall_norm = float(np.clip(fall_norm, 0.0, 1.0))

        else:
            # mode == "noise" — пороги уже в нормали
            # если вход был в метрах, to_norm01 сам разделит по ref_m из пакета (или бросит)
            try:
                height01 = to_norm01(src, fallback_ref=None, clip=True)
            except Exception:
                # если пакета нет (чистая нормаль ndarray), просто клипнем
                height01 = np.asarray(arr, dtype=np.float32)
                np.clip(height01, 0.0, 1.0, out=height01)
            thr_norm  = float(np.clip(thr,  0.0, 1.0))
            fall_norm = float(np.clip(fall, 0.0, 1.0))

        # 3) строим маску
        if which == "below":
            # 1 внизу, 0 вверху
            if fall_norm <= 0.0:
                mask = (height01 <= thr_norm).astype(np.float32)
            else:
                mask = 1.0 - self._smoothstep(thr_norm, thr_norm + fall_norm, height01.copy())
        else:
            # "above": 0 внизу, 1 вверху
            if fall_norm <= 0.0:
                mask = (height01 >= thr_norm).astype(np.float32)
            else:
                mask = self._smoothstep(thr_norm - fall_norm, thr_norm, height01.copy())

        self._clip01(mask)
        self._result_cache = mask
        return mask
