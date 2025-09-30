# generator_logic/core/composition.py
from __future__ import annotations
import numpy as np

def combine(A: np.ndarray, B: np.ndarray, mode: str, ratio: float = 0.5) -> np.ndarray:
    """
    Выполняет операцию смешивания двух массивов A и B.
    """
    # Приводим режим к нижнему регистру для надежности
    op = mode.lower()

    # Базовая арифметика
    if op == "add": return A + B
    if op == "subtract": return A - B
    if op == "multiply": return A * B
    if op == "divide": return A / (B + 1e-9)
    if op == "power": return np.power(A, B)
    if op == "min": return np.minimum(A, B)
    if op == "max": return np.maximum(A, B)
    if op == "difference": return np.abs(A - B)
    if op == "hypotenuse": return np.sqrt(A**2 + B**2)

    # Линейная интерполяция (Blend в Gaea)
    if op == "lerp":
        t = np.clip(ratio, 0.0, 1.0)
        return A * (1.0 - t) + B * t

    # Режимы наложения
    if op == "screen": return 1.0 - (1.0 - A) * (1.0 - B)
    if op == "overlay": return np.where(A < 0.5, 2.0 * A * B, 1.0 - 2.0 * (1.0 - A) * (1.0 - B))
    if op == "dodge": return np.clip(A / (1.0 - B + 1e-9), 0.0, 1.0)
    if op == "burn": return 1.0 - np.clip((1.0 - A) / (B + 1e-9), 0.0, 1.0)
    if op == "soft light":
        return np.where(B < 0.5,
                        (2 * A * B + A**2 * (1 - 2 * B)),
                        (2 * A * (1 - B) + np.sqrt(A) * (2 * B - 1)))
    if op == "hard light":
        return np.where(B < 0.5, 2 * A * B, 1 - 2 * (1 - A) * (1 - B))

    # Если операция неизвестна, возвращаем исходный массив A
    return A
