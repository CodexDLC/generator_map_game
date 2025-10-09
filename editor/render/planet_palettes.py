# editor/render/planet_palettes.py
from __future__ import annotations
from typing import List, Tuple
import numpy as np

# Палитры, предназначенные только для глобального вида планеты
PLANET_PALETTES: dict[str, List[Tuple[float, Tuple[int, int, int]]]] = {
    "Grayscale": [
        (0.0, (0, 0, 0)),  # Black
        (1.0, (255, 255, 255)),  # White
    ],
    # В будущем здесь могут быть палитры "Климат", "Температура" и т.д.
}


def map_planet_palette_cpu(z01: np.ndarray, name: str) -> np.ndarray:
    """
    Перевод нормализованных высот z∈[0,1] в RGB по единой палитре
    без разделения на сушу и воду.
    """
    z = np.clip(z01, 0.0, 1.0).astype(np.float32, copy=False)

    # Выбираем палитру, по умолчанию Grayscale
    stops = PLANET_PALETTES.get(name) or PLANET_PALETTES["Grayscale"]

    # Подготавливаем данные для интерполяции
    xs = np.array([p for p, _ in stops], dtype=np.float32)
    cols = np.array([[r, g, b] for _, (r, g, b) in stops], dtype=np.float32) / 255.0

    # Выполняем быструю линейную интерполяцию по всему массиву
    # np.interp требует 1D-массивы, поэтому временно "разворачиваем" z
    shape = z.shape
    z_flat = z.ravel()

    r = np.interp(z_flat, xs, cols[:, 0])
    g = np.interp(z_flat, xs, cols[:, 1])
    b = np.interp(z_flat, xs, cols[:, 2])

    # Собираем цвета обратно в 3D-массив (H, W, 3)
    rgb = np.stack([r, g, b], axis=-1)

    return rgb.reshape((*shape, 3)).astype(np.float32)