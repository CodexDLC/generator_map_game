import numpy as np


def _smoothstep(a, b, x):
    """Плавная S-образная интерполяция."""
    # Масштабируем x, чтобы он был в диапазоне [0, 1]
    t = np.clip((x - a) / (b - a), 0.0, 1.0)
    # Применяем формулу smoothstep
    return t * t * (3 - 2 * t)


def apply_edge_falloff(h01, cx, cy, cols, rows, falloff_width_px=64):
    """
    Применяет плавный спад ТОЛЬКО к внешним границам всей карты.
    """
    h, w = h01.shape

    # Клонируем массив, чтобы не изменять оригинал напрямую
    h01_modified = h01.copy()

    # Убедимся, что ширина спада не больше половины чанка
    falloff_width_px = min(falloff_width_px, w // 2, h // 2)
    if falloff_width_px <= 0: return h01_modified

    # Создаем одномерную маску спада от 0.0 до 1.0
    coords = np.arange(falloff_width_px)
    fade_in = _smoothstep(0.0, 1.0, coords / falloff_width_px)

    # Левый край всей карты
    if cx == 0:
        h01_modified[:, :falloff_width_px] *= fade_in

    # Правый край всей карты
    if cx == cols - 1:
        h01_modified[:, -falloff_width_px:] *= np.flip(fade_in)

    # Верхний край всей карты
    if cy == 0:
        h01_modified[:falloff_width_px, :] *= fade_in[:, np.newaxis]

    # Нижний край всей карты
    if cy == rows - 1:
        h01_modified[-falloff_width_px:, :] *= np.flip(fade_in)[:, np.newaxis]

    return h01_modified


def to_uint16(height01):
    import numpy as np
    arr = np.clip(height01, 0.0, 1.0)
    return np.round(arr * 65535.0).astype(np.uint16)