# generator_logic/terrain/global_sphere_noise.py
import logging
import numpy as np

from editor.utils.diag import diag_array
# --- НАЧАЛО ИЗМЕНЕНИЙ: Добавлен недостающий импорт ---
from game_engine_restructured.numerics.fast_noise_3d import simplex_noise_3d
# --- КОНЕЦ ИЗМЕНЕНИЙ ---

logger = logging.getLogger(__name__)


def _ensure_coords_array(coords_xyz):
    xyz = np.asarray(coords_xyz, dtype=np.float32)
    if xyz.ndim == 1 and xyz.shape[0] == 3:
        xyz = xyz.reshape((1, 1, 3))
    elif xyz.ndim == 2 and xyz.shape[-1] == 3:
        xyz = xyz[None, ...]
    elif not (xyz.ndim == 3 and xyz.shape[-1] == 3):
        raise ValueError(f"coords_xyz has unsupported shape {xyz.shape}; expected (..., 3)")
    return xyz.astype(np.float32)


def _calculate_base_noise(sphere_params: dict, coords_xyz: np.ndarray) -> np.ndarray:
    """
    Генерирует 3D мультифрактальный Simplex-шум.
    """
    xyz = _ensure_coords_array(coords_xyz)

    # --- НАЧАЛО ИЗМЕНЕНИЙ: Полностью новая логика с мультифрактальным циклом ---

    # Параметры из UI
    frequency = float(sphere_params.get('frequency', 4.0))
    octaves = int(sphere_params.get('octaves', 8))
    gain = float(sphere_params.get('gain', 0.5))  # Шероховатость
    seed = int(sphere_params.get('seed', 0)) & 0xFFFFFFFF

    # Параметры для мультифрактала (пока зашиты, потом можно вынести в UI)
    lacunarity = 2.0  # Насколько быстро увеличивается частота с каждой октавой
    H = 1.0 - gain  # Параметр Херста, контролирует "память" фрактала

    coords_x = xyz[..., 0]
    coords_y = xyz[..., 1]
    coords_z = xyz[..., 2]

    # Мультифрактальный цикл
    freq = frequency
    amp = 1.0
    total = np.zeros_like(coords_x, dtype=np.float32)

    for i in range(octaves):
        # Генерируем Simplex-шум для текущей октавы
        noise = simplex_noise_3d(coords_x * freq, coords_y * freq, coords_z * freq, seed + i)

        # Модулируем амплитуду на основе уже накопленного результата.
        # Это и есть суть мультифрактала: детализация зависит от общей формы.
        total += noise * amp * (total + 1.0)

        # Обновляем параметры для следующей октавы
        freq *= lacunarity
        amp *= gain

    diag_array(total, name="multifractal_raw")
    # --- КОНЕЦ ИЗМЕНЕНИЙ ---

    return total.astype(np.float32)


def get_noise_for_sphere_view(sphere_params: dict, coords_xyz: np.ndarray) -> np.ndarray:
    """
    Для 3D-вида всей планеты. Выполняет ЛОКАЛЬНУЮ нормализацию для максимального контраста.
    """
    noise_bipolar = _calculate_base_noise(sphere_params, coords_xyz)

    # --- ИЗМЕНЕНИЕ: Применяем Power здесь, до нормализации ---
    power = sphere_params.get('power', 1.0)
    if power != 1.0:
        # Для степенной функции нужно перевести диапазон в [0,1], применить и вернуть обратно
        noise_01 = (noise_bipolar + 1.0) * 0.5
        noise_01 = np.power(noise_01, power)
        noise_bipolar = noise_01 * 2.0 - 1.0
    # --- КОНЕЦ ИЗМЕНЕНИЯ ---

    mn, mx = float(np.nanmin(noise_bipolar)), float(np.nanmax(noise_bipolar))
    noise_01 = (noise_bipolar - mn) / (mx - mn) if mx > mn else np.zeros_like(noise_bipolar)
    return np.clip(noise_01, 0.0, 1.0).astype(np.float32)


def get_noise_for_region_preview(sphere_params: dict, coords_xyz: np.ndarray) -> np.ndarray:
    """
    Для превью региона. Выполняет ГЛОБАЛЬНУЮ нормализацию.
    """
    noise_bipolar = _calculate_base_noise(sphere_params, coords_xyz)
    noise_01 = (noise_bipolar + 1.0) * 0.5
    return np.clip(noise_01, 0.0, 1.0).astype(np.float32)