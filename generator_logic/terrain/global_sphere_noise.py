# generator_logic/terrain/global_sphere_noise.py
import logging
import numpy as np
from numpy.typing import NDArray

from editor.utils.diag import diag_array
from game_engine_restructured.numerics.fast_noise_3d import fbm_grid_3d, F32

logger = logging.getLogger(__name__)


def _ensure_coords_array(coords_xyz: NDArray[np.float32]) -> NDArray[np.float32]:
    """Гарантирует, что массив координат имеет правильную форму (H, W, 3)."""
    xyz = np.asarray(coords_xyz, dtype=np.float32)
    if xyz.ndim == 1 and xyz.shape[0] == 3:
        return xyz.reshape((1, 1, 3))
    if xyz.ndim == 2 and xyz.shape[-1] == 3:
        return xyz[:, np.newaxis, :]
    if not (xyz.ndim == 3 and xyz.shape[-1] == 3):
        raise ValueError(f"coords_xyz имеет неподдерживаемую форму {xyz.shape}; ожидалась (..., 3)")
    return xyz


def _calculate_base_noise(sphere_params: dict, coords_xyz: np.ndarray) -> np.ndarray:
    """
    Генерирует стабильный 3D FBM-шум, используя готовую реализацию.
    Возвращает шум в диапазоне [-1, 1] (с возможными небольшими выбросами).
    """
    xyz = _ensure_coords_array(coords_xyz)

    frequency = float(sphere_params.get('frequency', 4.0))
    octaves = int(sphere_params.get('octaves', 8))
    gain = float(sphere_params.get('gain', 0.5))
    seed = int(sphere_params.get('seed', 0)) & 0xFFFFFFFF
    ridge = bool(sphere_params.get('ridge', False))

    coords_x = xyz[..., 0]
    coords_y = xyz[..., 1]
    coords_z = xyz[..., 2]

    noise = fbm_grid_3d(
        seed=seed,
        coords_x=coords_x,
        coords_y=coords_y,
        coords_z=coords_z,
        freq0=F32(frequency),
        octaves=octaves,
        gain=F32(gain),
        ridge=ridge
    )

    diag_array(noise, name="fbm_3d_output")

    return noise.astype(np.float32)


def get_noise_for_sphere_view(sphere_params: dict, coords_xyz: np.ndarray) -> np.ndarray:
    """
    Для 3D-вида всей планеты. Выполняет ЛОКАЛЬНУЮ нормализацию для максимального контраста.
    """
    noise_bipolar = _calculate_base_noise(sphere_params, coords_xyz)

    power = sphere_params.get('power', 1.0)
    if power != 1.0:
        noise_01 = (noise_bipolar + 1.0) * 0.5
        # --- ИСПРАВЛЕНИЕ: Принудительно обрезаем диапазон перед возведением в степень ---
        noise_01 = np.clip(noise_01, 0.0, 1.0)
        noise_01 = np.power(noise_01, power)
        noise_bipolar = noise_01 * 2.0 - 1.0

    mn, mx = float(np.nanmin(noise_bipolar)), float(np.nanmax(noise_bipolar))
    if mx > mn:
        noise_01_local = (noise_bipolar - mn) / (mx - mn)
    else:
        noise_01_local = np.zeros_like(noise_bipolar)

    return np.clip(noise_01_local, 0.0, 1.0).astype(np.float32)


def get_noise_for_region_preview(sphere_params: dict, coords_xyz: np.ndarray) -> np.ndarray:
    """
    Для превью региона. Теперь использует ЛОКАЛЬНУЮ нормализацию для соответствия виду планеты.
    """
    noise_bipolar = _calculate_base_noise(sphere_params, coords_xyz)

    power = sphere_params.get('power', 1.0)
    if power != 1.0:
        # Применяем степень к нормализованному [0,1] диапазону
        noise_01 = (noise_bipolar + 1.0) * 0.5
        noise_01 = np.clip(noise_01, 0.0, 1.0)
        noise_01 = np.power(noise_01, power)
        noise_bipolar = noise_01 * 2.0 - 1.0

    # Локальная нормализация: растягиваем диапазон высот конкретного региона до [0, 1]
    mn, mx = float(np.nanmin(noise_bipolar)), float(np.nanmax(noise_bipolar))
    if mx > mn:
        noise_01_local = (noise_bipolar - mn) / (mx - mn)
    else:
        noise_01_local = np.zeros_like(noise_bipolar)

    return np.clip(noise_01_local, 0.0, 1.0).astype(np.float32)