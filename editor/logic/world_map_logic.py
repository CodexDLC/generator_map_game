# editor/logic/world_map_logic.py
from __future__ import annotations
import logging
import numpy as np
from PySide6 import QtGui
from PIL import Image
from PIL.ImageQt import ImageQt

from generator_logic.terrain.global_sphere_noise import global_sphere_noise_wrapper

logger = logging.getLogger(__name__)


def generate_world_map_image(
        sphere_params: dict,
        sea_level: float = 0.4,
        resolution: tuple[int, int] = (1024, 512)
) -> QtGui.QPixmap | None:
    """
    Генерирует 2D-карту мира (суша/вода) на основе глобальных настроек шума.

    Args:
        sphere_params: Словарь с параметрами для global_sphere_noise_wrapper.
        sea_level: Уровень моря (0..1) для разделения суши и воды.
        resolution: Разрешение генерируемой карты (ширина, высота).

    Returns:
        Готовый QPixmap для отображения или None в случае ошибки.
    """
    try:
        W, H = resolution
        # Контекст для генератора не требует реальных координат, только их форму
        x_coords, z_coords = np.meshgrid(np.zeros(W, dtype=np.float32), np.zeros(H, dtype=np.float32))
        context = {
            'project': {'seed': sphere_params.get('seed', 0)},
            'x_coords': x_coords,
            'z_coords': z_coords,
        }

        # Генерируем карту высот [0..1]
        height_map_01 = global_sphere_noise_wrapper(context, sphere_params, warp_params={})
        if height_map_01 is None:
            return None

        # Создаем цветное изображение: синий для воды, зеленый для суши
        land_color = (80, 140, 60)
        sea_color = (60, 90, 130)

        # Используем np.where для быстрой векторизованной раскраски
        color_map = np.where(
            height_map_01[..., np.newaxis] > sea_level,
            land_color,
            sea_color
        ).astype(np.uint8)

        # Конвертируем в QPixmap
        pil_img = Image.fromarray(color_map, mode='RGB')
        q_img = ImageQt(pil_img)
        return QtGui.QPixmap.fromImage(q_img)

    except Exception as e:
        logger.error(f"Ошибка при генерации карты мира: {e}", exc_info=True)
        return None


def calculate_offset_from_map_click(u: float, v: float, region_world_size: float) -> tuple[float, float]:
    """
    Рассчитывает смещение для основного превью по клику на карте.

    Args:
        u: Горизонтальная координата клика (0..1, слева направо).
        v: Вертикальная координата клика (0..1, сверху вниз).
        region_world_size: Размер мира, который отображается в основном превью (в метрах).

    Returns:
        Кортеж (offset_x, offset_z) для установки в UI.
    """
    # Карта мира представляет собой "развертку" с диапазоном координат
    # примерно в 2 раза шире, чем основной регион.
    # Это приближение, но оно интуитивно понятно.
    map_width = region_world_size * 2
    map_height = region_world_size

    # u=0.5, v=0.5 - это центр карты (0, 0)
    offset_x = (u - 0.5) * map_width
    offset_z = (v - 0.5) * map_height * -1  # Ось Z инвертирована

    return offset_x, offset_z