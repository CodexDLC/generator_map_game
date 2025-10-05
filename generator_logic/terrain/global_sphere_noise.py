# generator_logic/terrain/global_sphere_noise.py
import numpy as np
from game_engine_restructured.numerics.fast_noise import fbm_grid_3d


def _calculate_base_noise(sphere_params: dict, coords_xyz: np.ndarray) -> np.ndarray:
    """
    Внутренняя функция: генерирует "сырой" 3D FBM шум в диапазоне [-1, 1].
    """
    xyz = np.asarray(coords_xyz, dtype=np.float32)
    if xyz.ndim == 2 and xyz.shape[-1] == 3:
        xyz = xyz[None, ...]
    if xyz.ndim == 1 and xyz.shape[0] == 3:
        xyz = xyz[None, None, :]

    coords_x = xyz[..., 0]
    coords_y = xyz[..., 1]
    coords_z = xyz[..., 2]

    main_seed = int(sphere_params.get('seed', 0)) & 0xFFFFFFFF
    frequency = float(sphere_params.get('frequency', 1.0))

    coords_x *= frequency
    coords_y *= frequency
    coords_z *= frequency

    return fbm_grid_3d(
        seed=main_seed,
        coords_x=coords_x, coords_y=coords_y, coords_z=coords_z,
        freq0=1.0,
        octaves=int(sphere_params.get('octaves', 8)),
        gain=float(sphere_params.get('gain', 0.5)),
        ridge=bool(sphere_params.get('ridge', False))
    )


def get_noise_for_sphere_view(sphere_params: dict, coords_xyz: np.ndarray) -> np.ndarray:
    """
    Функция для 3D-вида всей планеты.
    Рассчитывает шум и растягивает его на локальный диапазон [0, 1] для
    максимальной контрастности отображения.
    """
    noise_bipolar = _calculate_base_noise(sphere_params, coords_xyz)

    # Растягиваем локальный диапазон для красивой картинки
    mn, mx = float(np.nanmin(noise_bipolar)), float(np.nanmax(noise_bipolar))
    if mx > mn:
        noise_01 = (noise_bipolar - mn) / (mx - mn)
    else:
        noise_01 = np.zeros_like(noise_bipolar)

    return np.clip(noise_01, 0.0, 1.0).astype(np.float32)


def get_noise_for_region_preview(sphere_params: dict, coords_xyz: np.ndarray) -> np.ndarray:
    """
    Функция для превью одного региона (плейна).
    Возвращает "честный" кусок глобального шума, преобразованный в [0, 1]
    без локального растягивания.
    """
    noise_bipolar = _calculate_base_noise(sphere_params, coords_xyz)

    # "Честное" преобразование диапазона [-1, 1] в [0, 1]
    noise_01 = (noise_bipolar + 1.0) * 0.5

    return np.clip(noise_01, 0.0, 1.0).astype(np.float32)