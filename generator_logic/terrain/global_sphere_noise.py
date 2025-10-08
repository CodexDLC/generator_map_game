# generator_logic/terrain/global_sphere_noise.py
import logging
import numpy as np
from game_engine_restructured.numerics.fast_noise import fbm_grid_3d
from editor.utils.diag import diag_array

logger = logging.getLogger(__name__)


def _ensure_coords_array(coords_xyz):
    """
    Нормализует coords_xyz к форме (H, W, 3) или (1, 1, 3) и возвращает массив float32.
    """
    xyz = np.asarray(coords_xyz, dtype=np.float32)

    # Приводим к форме (H, W, 3) или (1, 1, 3)
    if xyz.ndim == 1 and xyz.shape[0] == 3:
        xyz = xyz.reshape((1, 1, 3))
    elif xyz.ndim == 2 and xyz.shape[-1] == 3:
        xyz = xyz[None, ...]
    elif xyz.ndim == 3 and xyz.shape[-1] == 3:
        pass
    else:
        raise ValueError(f"coords_xyz has unsupported shape {xyz.shape}; expected (..., 3)")

    return xyz.astype(np.float32)


def _coords_is_constant(xyz: np.ndarray) -> bool:
    """
    Проверяет, все ли координаты одинаковы (по всем каналам).
    """
    if xyz.ndim == 3:
        mn = xyz.min(axis=(0, 1))
        mx = xyz.max(axis=(0, 1))
    else:
        mn = xyz.min(axis=0)
        mx = xyz.max(axis=0)
    return np.allclose(mn, mx)


def _calculate_base_noise(sphere_params: dict, coords_xyz: np.ndarray) -> np.ndarray:
    """
    Генерирует "сырой" 3D FBM шум в диапазоне [-1, 1].
    Добавлена диагностика входов/выходов через diag_array.
    """
    xyz = _ensure_coords_array(coords_xyz)

    # Диагностика входных координат
    logger.debug("global_sphere_noise: _calculate_base_noise called. coords_xyz shape=%s", xyz.shape)
    diag_array(xyz, name="coords_xyz (input)")

    # Проверка на однородность координат — частая причина константного шума
    if _coords_is_constant(xyz):
        logger.warning(
            "global_sphere_noise: coords_xyz appears constant (every pixel same vector). "
            "This will produce constant FBM output. first_vector=%s", xyz.reshape(-1, 3)[0].tolist()
        )

    coords_x = xyz[..., 0]
    coords_y = xyz[..., 1]
    coords_z = xyz[..., 2]

    main_seed = int(sphere_params.get('seed', 0)) & 0xFFFFFFFF

    # Преобразование UI scale -> frequency
    scale_value = float(sphere_params.get('scale', 0.25))
    frequency = 1.0 + (scale_value * 9.0)

    # Защита аргументов
    octaves = int(sphere_params.get('octaves', 8))
    if octaves < 1:
        logger.warning("octaves < 1 (%s) — forcing to 1", octaves)
        octaves = 1
    if octaves > 16:
        logger.warning("octaves > 16 (%s) — clamping to 16", octaves)
        octaves = 16

    gain = float(sphere_params.get('gain', 0.5))
    ridge = bool(sphere_params.get('ridge', False))

    # Вызов FBM
    noise = fbm_grid_3d(
        seed=main_seed,
        coords_x=coords_x, coords_y=coords_y, coords_z=coords_z,
        freq0=frequency,
        octaves=octaves,
        gain=gain,
        ridge=ridge
    )

    # Диагностика выхода шума
    logger.debug("global_sphere_noise: fbm_grid_3d produced noise")
    diag_array(noise, name="noise_bipolar (raw fbm)")

    return noise


def get_noise_for_sphere_view(sphere_params: dict, coords_xyz: np.ndarray) -> np.ndarray:
    """
    Для 3D-вида всей планеты: масштабируем локально в [0,1] для контраста.
    """
    noise_bipolar = _calculate_base_noise(sphere_params, coords_xyz)

    # диагностика перед нормализацией
    diag_array(noise_bipolar, name="noise_bipolar (before normalize)")

    mn, mx = float(np.nanmin(noise_bipolar)), float(np.nanmax(noise_bipolar))
    if mx > mn:
        noise_01 = (noise_bipolar - mn) / (mx - mn)
    else:
        logger.warning(
            "get_noise_for_sphere_view: noise_bipolar is constant (mn==mx). "
            "Returning small procedural fallback for preview."
        )
        rng = np.random.RandomState(int(sphere_params.get('seed', 0)) & 0xFFFFFFFF)
        fallback = rng.rand(*noise_bipolar.shape).astype(np.float32) * 1e-3
        noise_01 = fallback

    diag_array(noise_01, name="noise_01 (sphere_view)")

    return np.clip(noise_01, 0.0, 1.0).astype(np.float32)


def get_noise_for_region_preview(sphere_params: dict, coords_xyz: np.ndarray) -> np.ndarray:
    """
    Для превью региона: честное преобразование [-1,1] -> [0,1].
    """
    noise_bipolar = _calculate_base_noise(sphere_params, coords_xyz)

    diag_array(noise_bipolar, name="noise_bipolar (region preview before mapping)")

    mn, mx = float(np.nanmin(noise_bipolar)), float(np.nanmax(noise_bipolar))
    if mx == mn:
        logger.warning("get_noise_for_region_preview: noise is constant (mn==mx==%s). seed=%s",
                       mn, sphere_params.get("seed", None))
        rng = np.random.RandomState(int(sphere_params.get('seed', 0)) & 0xFFFFFFFF)
        fallback = np.clip((rng.rand(*noise_bipolar.shape) * 0.01), 0.0, 1.0).astype(np.float32)
        diag_array(fallback, name="fallback_noise (region preview)")
        return fallback

    noise_01 = (noise_bipolar + 1.0) * 0.5
    diag_array(noise_01, name="noise_01 (region preview)")

    return np.clip(noise_01, 0.0, 1.0).astype(np.float32)
