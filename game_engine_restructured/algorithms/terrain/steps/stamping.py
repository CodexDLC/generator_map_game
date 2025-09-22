# Файл: game_engine_restructured/algorithms/terrain/steps/stamping.py

from __future__ import annotations
import math
import os
from typing import Dict, Any
import numpy as np
from PIL import Image

from game_engine_restructured.algorithms.terrain.uber_blend import smoothstep

# Кэш для хранения загруженных текстур, чтобы не читать их с диска каждый раз
STAMP_CACHE: Dict[str, np.ndarray] = {}


def _load_stamp_texture(path: str) -> np.ndarray | None:
    """Вспомогательная функция: загружает текстуру-штамп, проверяет формат и кэширует ее."""
    if not os.path.exists(path):
        print(f"!!! [Stamping] CRITICAL ERROR: Файл штампа не найден по пути: {path}")
        return None

    if path in STAMP_CACHE:
        return STAMP_CACHE[path]
    try:
        with Image.open(path) as img:
            # Убедимся, что изображение в оттенках серого для корректной работы
            stamp_image = img.convert("L")
            stamp_array = np.array(stamp_image, dtype=np.float32)

        # Проверяем, 16-битное ли изображение для правильной нормализации
        is_16bit = 'uint16' in str(stamp_array.dtype) or (hasattr(img, 'mode') and ('I;16' in img.mode))
        max_val = 65535.0 if is_16bit else 255.0

        normalized_stamp = stamp_array / max_val
        STAMP_CACHE[path] = normalized_stamp
        print(f"    [Stamping] -> Текстура-штамп '{path}' успешно загружена и кэширована.")
        return normalized_stamp

    except Exception as e:
        print(f"!!! [Stamping] CRITICAL ERROR: Не удалось загрузить штамп '{path}': {e}")
        return None


def generate_displacement(
        x_coords: np.ndarray,
        z_coords: np.ndarray,
        cell_size: float,
        stamp_params: Dict[str, Any]
) -> np.ndarray:
    """
    Создает карту смещения высот на основе текстуры-штампа.
    Не меняет рельеф напрямую, а возвращает массив для дальнейшего использования.
    """
    stamp_path = stamp_params.get("path")
    if not stamp_path:
        return np.zeros_like(x_coords)

    stamp_texture = _load_stamp_texture(stamp_path)
    if stamp_texture is None:
        return np.zeros_like(x_coords)

    # Читаем параметры из словаря `stamp_params`
    amp_m = float(stamp_params.get("amp_m", 0.0))
    scale_tiles = float(stamp_params.get("scale_tiles", 500.0))

    # Рассчитываем, как часто текстура будет повторяться (тайлиться)
    texture_frequency = 1.0 / (scale_tiles * cell_size + 1e-6)

    tex_height, tex_width = stamp_texture.shape

    # Вычисляем UV-координаты для сэмплирования из текстуры
    u_coords = (x_coords * texture_frequency * tex_width)
    v_coords = (z_coords * texture_frequency * tex_height)

    # Применяем "зацикливание" (тайлинг) через оператор остатка от деления
    u_indices = (u_coords % tex_width).astype(np.int32)
    v_indices = (v_coords % tex_height).astype(np.int32)

    # Берем значения из текстуры по вычисленным индексам
    sampled_values = stamp_texture[v_indices, u_indices]

    # Возвращаем карту смещения (значение штампа [0..1] * сила в метрах)
    return (sampled_values * amp_m).astype(np.float32)


def generate_decal(
        x_coords: np.ndarray,
        z_coords: np.ndarray,
        cell_size: float,
        stamp_params: Dict[str, Any],
        *,
        center_x: float,
        center_z: float,
        angle_deg: float = 0.0
) -> np.ndarray:
    """
    Генерирует одиночный штамп ("декаль") с поворотом и плавными краями.
    """
    stamp_path = stamp_params.get("path")
    stamp_texture = _load_stamp_texture(stamp_path)
    if stamp_texture is None:
        return np.zeros_like(x_coords)

    amp_m = float(stamp_params.get("amp_m", 0.0))
    scale_m = float(stamp_params.get("scale_tiles", 500.0)) * cell_size
    falloff_range = float(stamp_params.get("falloff_range", 0.0))

    # 1. Трансформация координат: сдвиг, поворот, масштабирование
    dx = x_coords - center_x
    dz = z_coords - center_z

    angle_rad = math.radians(angle_deg)
    cos_a = math.cos(angle_rad)
    sin_a = math.sin(angle_rad)

    dx_rot = dx * cos_a - dz * sin_a
    dz_rot = dx * sin_a + dz * cos_a

    # Переводим в UV-координаты [0..1]
    u = (dx_rot / scale_m) + 0.5
    v = (dz_rot / scale_m) + 0.5

    # 2. Создаем маску затухания (falloff)
    if falloff_range > 0.0:
        # Расстояние от центра в UV-координатах (от 0 до ~0.7)
        dist_from_center_sq = (u - 0.5) ** 2 + (v - 0.5) ** 2
        # Плавный переход от 1 (внутри) к 0 (на краях)
        falloff_mask = 1.0 - smoothstep(
            (0.5 - 0.5 * falloff_range) ** 2,
            0.5 ** 2,
            dist_from_center_sq
        )
    else:
        falloff_mask = 1.0

    # 3. Сэмплируем текстуру, но только внутри "декали"
    tex_h, tex_w = stamp_texture.shape
    u_indices = (u * tex_w).astype(np.int32)
    v_indices = (v * tex_h).astype(np.int32)

    np.clip(u_indices, 0, tex_w - 1, out=u_indices)
    np.clip(v_indices, 0, tex_h - 1, out=v_indices)

    # Создаем маску, чтобы брать пиксели только из области [0,1]
    valid_mask = (u >= 0) & (u <= 1) & (v >= 0) & (v <= 1)

    sampled_values = np.zeros_like(x_coords, dtype=np.float32)
    if np.any(valid_mask):
        # Берем значения из текстуры только для валидных индексов
        sampled_values[valid_mask] = stamp_texture[v_indices[valid_mask], u_indices[valid_mask]]

    # 4. Применяем амплитуду и маску затухания
    return (sampled_values * amp_m * falloff_mask).astype(np.float32)