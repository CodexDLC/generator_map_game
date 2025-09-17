import numpy as np
from numba import njit, prange


@njit(cache=True, fastmath=True, parallel=True)
def create_mask(base_noise: np.ndarray, threshold: float, invert: bool, fade_range: float) -> np.ndarray:
    """
    Создает маску [0,1] из базового шума по заданным правилам порога, инверсии и плавного перехода.
    """
    h, w = base_noise.shape
    output = np.empty_like(base_noise)

    # Определяем границы плавного перехода (fade)
    fade_half = max(0.0, fade_range / 2.0)
    t0 = threshold - fade_half
    t1 = threshold + fade_half

    for i in prange(h):
        for j in range(w):
            val = base_noise[i, j]

            # Рассчитываем положение точки внутри зоны перехода [0, 1]
            t = (val - t0) / (t1 - t0) if (t1 - t0) > 1e-6 else 0.0

            # Ограничиваем t в диапазоне [0, 1]
            t = max(0.0, min(1.0, t))

            # Применяем формулу Smoothstep для S-образного плавного перехода
            smooth_val = t * t * (3.0 - 2.0 * t)

            if invert:
                output[i, j] = 1.0 - smooth_val
            else:
                output[i, j] = smooth_val

    return output