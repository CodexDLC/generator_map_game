# generator_logic/terrain/easy_erosion.py
from __future__ import annotations
import numpy as np

# Для простого размытия используем OpenCV (opencv-python есть в requirements)
try:
    import cv2
except ImportError:
    cv2 = None

def easy_erosion_wrapper(context: dict, height_map: np.ndarray, params: dict) -> np.ndarray:
    """
    Простая эрозия-приглаживание: сглаживает карту высот и смешивает её
    с оригиналом. Создаёт эффект, будто острые края присыпаны песком.

    :param context: словарь контекста проекта (WORLD_SIZE_METERS и пр.).
    :param height_map: входная карта высот (H x W, float32).
    :param params: dict со следующими ключами:
        - influence (float 0..1): сила смешивания. 0 = без изменений,
          1 = полностью сглаженная карта.
        - kernel_size (int): размер ядра размытия (должно быть нечётным).
        - iterations (int): сколько раз размытие применяется последовательно.
    :return: новая карта высот (float32).
    """
    if cv2 is None:
        # OpenCV не установлен — возвращаем оригинал
        return height_map

    influence = float(params.get("influence", 0.5))
    kernel_size = int(params.get("kernel_size", 11))
    iterations = int(params.get("iterations", 1))

    # ядро размытия должно быть нечётным и >= 3
    k = max(3, kernel_size | 1)

    # копируем карту для обработки
    z = height_map.astype(np.float32, copy=True)
    blurred = z.copy()

    # многократное размытие усиливает эффект
    for _ in range(max(1, iterations)):
        blurred = cv2.GaussianBlur(blurred, (k, k), 0)

    # смешиваем оригинал и размытие
    new_z = z * (1.0 - influence) + blurred * influence

    return new_z.astype(np.float32)
