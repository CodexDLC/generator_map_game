# generator_logic/terrain/global_sphere_noise.py
import logging
import numpy as np
from game_engine_restructured.numerics.fast_noise import fbm_grid_3d
from editor.utils.diag import diag_array

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
    Генерирует "сырой" 3D FBM шум. Ожидает на вход координаты на единичной сфере [-1, 1].
    Возвращает результат, нормализованный по аналитической амплитуде (~[-1, 1]).
    """
    xyz = _ensure_coords_array(coords_xyz)
    logger.debug("global_sphere_noise: _calculate_base_noise called. coords_xyz shape=%s", xyz.shape)
    diag_array(xyz, name="coords_xyz (input)")

    scale_value = float(sphere_params.get('scale', 0.25))
    frequency = 1.0 + (scale_value * 9.0)

    coords_x, coords_y, coords_z = xyz[..., 0], xyz[..., 1], xyz[..., 2]

    main_seed = int(sphere_params.get('seed', 0)) & 0xFFFFFFFF
    octaves = int(sphere_params.get('octaves', 8))
    gain = float(sphere_params.get('gain', 0.5))
    ridge = bool(sphere_params.get('ridge', False))

    # Эта функция ДОЛЖНА возвращать шум в диапазоне [-1, 1], но сейчас в ней есть баг со смещением
    noise = fbm_grid_3d(
        seed=main_seed,
        coords_x=coords_x, coords_y=coords_y, coords_z=coords_z,
        freq0=frequency,
        octaves=octaves,
        gain=gain,
        ridge=ridge
    )

    diag_array(noise, name="noise_bipolar (from fbm_grid_3d)")

    # ВРЕМЕННЫЙ КОСТЫЛЬ для исправления бага со смещением в fbm_grid_3d
    # Теоретически, среднее значение FBM шума должно быть близко к 0.
    # В логах мы видим, что оно ~10.0. Мы вычитаем это смещение.
    observed_mean = np.mean(noise)
    if abs(observed_mean) > 2.0:  # Если смещение аномально большое
        logger.warning(f"fbm_grid_3d имеет большое смещение ({observed_mean:.2f}). Принудительно центрируем.")
        noise -= observed_mean

    return noise.astype(np.float32)


def get_noise_for_sphere_view(sphere_params: dict, coords_xyz: np.ndarray) -> np.ndarray:
    """
    Для 3D-вида всей планеты. Выполняет ЛОКАЛЬНУЮ нормализацию для максимального контраста.
    """
    noise_bipolar = _calculate_base_noise(sphere_params, coords_xyz)
    mn, mx = float(np.nanmin(noise_bipolar)), float(np.nanmax(noise_bipolar))
    # Растягиваем локальный диапазон на [0,1] для лучшей картинки на глобусе
    noise_01 = (noise_bipolar - mn) / (mx - mn) if mx > mn else np.zeros_like(noise_bipolar)
    return np.clip(noise_01, 0.0, 1.0).astype(np.float32)


def get_noise_for_region_preview(sphere_params: dict, coords_xyz: np.ndarray) -> np.ndarray:
    """
    Для превью региона. Выполняет ГЛОБАЛЬНУЮ нормализацию.
    """
    noise_bipolar = _calculate_base_noise(sphere_params, coords_xyz)
    # Просто отображаем теоретический диапазон [-1, 1] в [0, 1] без растягивания.
    # Это гарантирует, что плоские регионы останутся плоскими.
    noise_01 = (noise_bipolar + 1.0) * 0.5
    return np.clip(noise_01, 0.0, 1.0).astype(np.float32)