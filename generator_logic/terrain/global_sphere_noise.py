# generator_logic/terrain/global_sphere_noise.py
import numpy as np
from game_engine_restructured.numerics.fast_noise import fbm_grid_3d


def global_sphere_noise_wrapper(context: dict, sphere_params: dict, **kwargs) -> np.ndarray:
    """
    Генерирует 3D FBM шум для переданного набора 3D координат.
    Возвращает нормализованный массив [0..1].
    """
    # Получаем 3D координаты из нового, обязательного аргумента
    coords_xyz = kwargs.get("coords_xyz")
    if coords_xyz is None:
        raise ValueError("global_sphere_noise_wrapper теперь требует аргумент 'coords_xyz'")

    # --- PATCH 1: Устойчивый wrapper для формы входных данных ---
    xyz = np.asarray(coords_xyz, dtype=np.float32)
    if xyz.ndim == 2 and xyz.shape[-1] == 3:
        xyz = xyz[None, ...]  # (1, N, 3) — если пришёл батч точек
    if xyz.ndim == 1 and xyz.shape[0] == 3:
        xyz = xyz[None, None, :]  # (1, 1, 3) — одиночная точка

    # Распаковка координат
    coords_x = xyz[..., 0]
    coords_y = xyz[..., 1]
    coords_z = xyz[..., 2]
    # --- END PATCH 1 ---

    world_seed = int(context.get('project', {}).get('seed', 0))
    seed_offset = int(sphere_params.get('seed', 0))
    main_seed = (world_seed ^ seed_offset) & 0xFFFFFFFF
    frequency = float(sphere_params.get('frequency', 1.0))

    # Масштабируем координаты для получения нужной частоты шума
    coords_x = coords_x * frequency
    coords_y = coords_y * frequency
    coords_z = coords_z * frequency

    # Вызываем ядро генерации шума
    noise_np = fbm_grid_3d(
        seed=main_seed,
        coords_x=coords_x, coords_y=coords_y, coords_z=coords_z,
        freq0=1.0,
        octaves=int(sphere_params.get('octaves', 8)),
        gain=float(sphere_params.get('gain', 0.5)),
        ridge=bool(sphere_params.get('ridge', False))
    )

    # Нормализуем результат в диапазон [0..1]
    mn, mx = float(np.nanmin(noise_np)), float(np.nanmax(noise_np))
    if mx > mn:
        noise_np = (noise_np - mn) / (mx - mn)

    return np.clip(noise_np, 0.0, 1.0).astype(np.float32)
