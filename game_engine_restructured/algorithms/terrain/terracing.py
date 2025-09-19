# ==============================================================================
# Файл: game_engine_restructured/algorithms/terrain/terracing.py
# ВЕРСИЯ 2.0: "Умные террасы", которые учитывают форму рельефа.
# ==============================================================================
from __future__ import annotations
import numpy as np
from typing import Any, Dict

# Импортируем "математику" из numerics и core
from ...numerics.fast_noise import fbm_grid_warped_bipolar
from scipy.ndimage import gaussian_filter


def _calculate_curvature(height_grid: np.ndarray, cell_size: float) -> np.ndarray:
    """
    Рассчитывает кривизну поверхности (Лапласиан).
    Высокие значения означают острые хребты или глубокие лощины.
    """
    # Сначала немного сглаживаем высоты, чтобы уменьшить шум в производных
    smoothed_h = gaussian_filter(height_grid, sigma=1.5, mode='reflect')

    # Вычисляем вторые производные
    gyy, gxx = np.gradient(np.gradient(smoothed_h, cell_size, axis=0), cell_size, axis=0), \
        np.gradient(np.gradient(smoothed_h, cell_size, axis=1), cell_size, axis=1)

    # Лапласиан - это сумма вторых производных. Берем его модуль.
    curvature = np.abs(gxx + gyy)
    return curvature


def apply_terracing_effect(
        height_grid: np.ndarray,
        mask_strength: np.ndarray,
        cfg: Dict[str, Any],
        *,
        seed: int = 0,
        x_coords: np.ndarray | None = None,
        z_coords: np.ndarray | None = None,
        cell_size: float = 1.0
) -> np.ndarray:
    """
    "Умное" террасирование, которое следует за рельефом.
    """
    if not bool(cfg.get("enabled", True)):
        return height_grid

    print("[Terrace] -> Применение нового алгоритма 'умных' террас...")

    step_h = float(cfg.get("step_height_m", 60.0))
    ledge_ratio = float(cfg.get("ledge_ratio", 0.7))
    strength_m = float(cfg.get("strength_m", 10.0))
    rnd: Dict[str, Any] = cfg.get("randomization", {}) or {}

    # --- ШАГ 1: Базовая форма террас по высоте (решает проблему "растягивания") ---
    # "Фаза" теперь напрямую зависит от высоты, заставляя ступени следовать линиям высот.
    phase = (height_grid / step_h) % 1.0  # [0..1)

    # --- ШАГ 2: Рандомизация, которая "обтекает" рельеф ---
    # Рассчитываем направление склона (градиент)
    gz, gx = np.gradient(height_grid, cell_size)

    # Используем градиент для искажения координат шума (Domain Warping)
    warp_strength = float(rnd.get("warp_strength", 25.0))
    warped_x = x_coords + gx * warp_strength
    warped_z = z_coords + gz * warp_strength

    # Генерируем шум для случайных деталей на "искаженных" координатах
    ledge_jitter = float(rnd.get("ledge_jitter", 0.0))
    ledge_scale = float(rnd.get("ledge_scale_tiles", 3000.0))
    if ledge_jitter != 0.0:
        # Конфиг для генератора шума
        ledge_noise_cfg = {
            "amp_m": 1.0,
            "scale_tiles": ledge_scale,
            "octaves": 2
        }
        # Генерируем шум в диапазоне [-1, 1]
        n_ledge = fbm_grid_warped_bipolar(
            seed=seed + 23,
            coords_x=warped_x,
            coords_z=warped_z,
            freq0=1.0 / (ledge_scale * cell_size),
            octaves=2,
            ridge=True
        )
        ledge_local = np.clip(ledge_ratio * (1.0 + ledge_jitter * n_ledge), 0.5, 0.9)
    else:
        ledge_local = np.full_like(height_grid, np.clip(ledge_ratio, 0.05, 0.95))

    # --- ШАГ 3: Формирование деформации ---
    # Формула "колокола" для создания уступов и склонов
    u = np.where(phase < ledge_local, phase / np.maximum(ledge_local, 1e-6),
                 (phase - ledge_local) / np.maximum(1.0 - ledge_local, 1e-6))
    bell = 1.0 - (2.0 * u - 1.0) ** 2
    sign = np.where(phase < ledge_local, 1.0, -0.75)
    deformation = sign * bell * strength_m

    # --- ШАГ 4: Логичные разрывы террас по кривизне ---
    print("[Terrace] -> Расчет кривизны для маски разрывов...")
    curvature = _calculate_curvature(height_grid, cell_size)

    # Нормализуем кривизну, чтобы получить значения ~[0, 1]
    # Используем 95-й перцентиль, чтобы редкие экстремальные значения не портили картину
    p95 = np.percentile(curvature, 95)
    curvature_norm = np.clip(curvature / (p95 + 1e-6), 0, 1)

    # Создаем "маску разрывов": где кривизна высокая, там террасы слабее.
    # `curvature_fade` из пресета теперь контролирует, насколько сильно кривизна влияет на разрывы
    break_fade = max(1e-6, float(rnd.get("curvature_fade", 0.5)))
    break_mask = 1.0 - np.power(curvature_norm, break_fade)

    # --- ШАГ 5: Финальное применение ---
    # Умножаем деформацию на маску разрывов и на общую маску силы эффекта
    final_deformation = deformation * break_mask * mask_strength

    final_height = height_grid + final_deformation

    print("[Terrace] -> 'Умные' террасы успешно применены.")
    # _print_range("After Smart Terracing", final_height)

    return final_height