# generator_logic/masks/shape_masks.py
from __future__ import annotations
import numpy as np
# --- ДОБАВЬ ЭТИ ИМПОРТЫ ---
from numba import njit, prange
import math # Убедись, что math импортирован
# --- КОНЕЦ ДОБАВЛЕНИЙ ---

# --- КОНСТАНТА ДЛЯ ИЗБЕЖАНИЯ ДЕЛЕНИЯ НА НОЛЬ ---
EPS = 1e-9
F32 = np.float32 # Определяем F32 здесь

@njit(inline='always')
def smoothstep_scalar(edge0: F32, edge1: F32, x: F32) -> F32:
    denom = edge1 - edge0
    if denom < EPS:
        return F32(1.0) if x >= edge1 else F32(0.0)
    t = (x - edge0) / denom
    if t < F32(0.0): t = F32(0.0)
    elif t > F32(1.0): t = F32(1.0)
    return F32(t * t * F32(3.0) - t * t * t * F32(2.0))

# --- Ядро генерации ГЕКСАГОНАЛЬНОЙ маски - ИСПРАВЛЕННАЯ ВЕРСИЯ ---
@njit(cache=True, fastmath=True, parallel=True)
def generate_hexagonal_mask_kernel(
        output_mask: np.ndarray,
        x_coords: np.ndarray,
        z_coords: np.ndarray,
        outer_radius_m: float, # Используется для нормализации координат
        fade_ratio: float      # Доля от края внутрь для затухания (0=резко, 1=от центра)
):
    """
    Генерирует 2D маску ГЕКСАГОНА [0..1]. Значение 1 в центре, плавно
    спадает до 0 ровно на границе гексагона. Fade_ratio контролирует ширину спада.
    """
    H, W = x_coords.shape
    outer_radius_m_f32 = F32(max(outer_radius_m, EPS))
    inv_outer_radius = F32(1.0 / outer_radius_m_f32)

    # Границы для smoothstep в нормализованном гексагональном расстоянии [0..1]
    # fade_end_norm всегда 1.0 (граница гексагона)
    # fade_start_norm - где начинается спад (ближе к центру)
    fade_end_norm = F32(1.0)
    fade_start_norm = F32(1.0 - max(0.0, min(1.0, fade_ratio)))

    # Константы для гексагональной метрики (pointy-top)
    sqrt3_div_2 = F32(math.sqrt(3.0) / 2.0)

    for r in prange(H):
        for c in range(W):
            x = F32(x_coords[r, c])
            z = F32(z_coords[r, c]) # Используем z

            # Нормализуем координаты относительно ВНЕШНЕГО радиуса
            nx = x * inv_outer_radius
            nz = z * inv_outer_radius # Используем z
            hx = F32(abs(nx))
            hz = F32(abs(nz)) # Используем z

            # --- Вычисляем "гексагональное расстояние" от центра ---
            # Это значение будет ~0 в центре и достигнет ~sqrt3_div_2 на границе ребра
            # Используем условие границы: hx * sqrt3_div_2 + hz * 0.5
            hex_dist_val = hx * sqrt3_div_2 + hz * F32(0.5)

            # --- Нормализуем гексагональное расстояние к диапазону [0..1] ---
            # Делим на максимальное значение, которое достигается на границе (sqrt3_div_2)
            # Добавляем EPS для защиты от деления на ноль, если радиус очень мал
            norm_hex_dist = hex_dist_val / (sqrt3_div_2 + EPS)
            # Ограничиваем сверху 1.0 на случай неточностей вычислений
            norm_hex_dist = min(norm_hex_dist, F32(1.0))

            # --- Проверяем, находится ли точка ВНЕ гексагона ---
            # Используем чуть более строгую проверку из-за нормализации
            # Если norm_hex_dist > 1.0 ИЛИ точка выходит за вертикальные пределы pointy-top (|nz| > 1.0)
            if norm_hex_dist > F32(1.0) or hz > F32(1.0):
                 output_mask[r, c] = F32(0.0)
                 continue

            # --- Применяем smoothstep к нормализованному гекс. расстоянию ---
            # smoothstep(start, end, val) -> плавно от 0 до 1
            # 1.0 - smoothstep(...) -> плавно от 1 до 0
            mask_value = F32(1.0) - smoothstep_scalar(fade_start_norm, fade_end_norm, norm_hex_dist)
            output_mask[r, c] = mask_value

# --- Обёртка (wrapper) для гексагональной маски ---
def generate_hexagonal_mask(
    context: dict,
    fade_ratio: float = 0.15 # Ширина затухания как доля от радиуса вписанной окружности к описанной
) -> np.ndarray:
    """
    Создает гексагональную маску региона [0..1] на основе данных из context.
    Затухание происходит от границы вписанной окружности к границе гексагона.
    """
    x_coords = context['x_coords']
    z_coords = context['z_coords']
    world_size_m = context.get('WORLD_SIZE_METERS', 1000.0)

    # Радиус описанной окружности гексагона - половина размера мира
    outer_radius_m = world_size_m / 2.0

    output_mask = np.empty(x_coords.shape, dtype=np.float32)

    generate_hexagonal_mask_kernel(
        output_mask,
        x_coords,
        z_coords,
        outer_radius_m,
        fade_ratio # Передаем fade_ratio напрямую
    )
    return output_mask