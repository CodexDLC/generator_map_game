# generator_logic/terrain/global_sphere_noise.py
import numpy as np
from game_engine_restructured.numerics.fast_noise import fbm_grid_3d
from generator_logic.core.warp import apply_domain_warp


def global_sphere_noise_wrapper(context: dict, sphere_params: dict, warp_params: dict):
    """
    Генерирует глобальный шум на основе цилиндрической проекции
    и применяет маску полярных океанов.
    """
    H, W = context['x_coords'].shape
    world_seed = int(context.get('project', {}).get('seed', 0))

    # --- Параметры из UI ---
    seed_offset = int(sphere_params.get('seed', 0))
    main_seed = (world_seed ^ seed_offset) & 0xFFFFFFFF
    frequency = float(sphere_params.get('frequency', 8.0))

    ocean_start_latitude = float(sphere_params.get('ocean_latitude', 75.0))
    ocean_falloff_deg = float(sphere_params.get('ocean_falloff', 10.0))

    # --- 1. Генерация цилиндрического шума ---

    # Создаем сетку координат: долгота (phi) и широта (latitude)
    phi = np.linspace(0, 2 * np.pi, W, dtype=np.float32)  # 0 to 360 degrees
    latitude = np.linspace(-90, 90, H, dtype=np.float32)  # -90 (юг) to +90 (север)
    phi_grid, latitude_grid = np.meshgrid(phi, latitude)

    # Преобразуем долготу в X,Y на окружности. Широту используем как Z.
    # Это "разворачивает" цилиндр в 3D пространстве для шума.
    nx = np.cos(phi_grid)
    ny = np.sin(phi_grid)
    nz = latitude_grid / 90.0  # Нормализуем широту в [-1, 1]

    # Применяем частоту
    coords_x = nx * frequency
    coords_y = ny * frequency
    coords_z = nz * frequency

    # Вызываем 3D FBM
    noise = fbm_grid_3d(
        seed=main_seed,
        coords_x=coords_x, coords_y=coords_y, coords_z=coords_z,
        freq0=1.0,  # Частота уже применена
        octaves=int(sphere_params.get('octaves', 8)),
        gain=float(sphere_params.get('gain', 0.5)),
        ridge=bool(sphere_params.get('ridge', False))
    )
    noise_01 = (noise + 1.0) * 0.5

    # --- 2. Создание и применение маски полярных океанов ---

    # abs(latitude_grid) - расстояние в градусах от экватора
    abs_latitude = np.abs(latitude_grid)

    # Вычисляем границы плавного перехода
    edge0 = ocean_start_latitude - ocean_falloff_deg
    edge1 = ocean_start_latitude

    # t будет от 0 (на суше) до 1 (в полярной шапке)
    t = np.clip((abs_latitude - edge0) / (edge1 - edge0 + 1e-6), 0.0, 1.0)
    # Применяем smoothstep для плавности
    t_smooth = t * t * (3.0 - 2.0 * t)

    polar_mask = 1.0 - t_smooth

    # Умножаем карту высот на маску, чтобы плавно опустить полюса до 0
    final_noise = noise_01 * polar_mask

    return final_noise.astype(np.float32)