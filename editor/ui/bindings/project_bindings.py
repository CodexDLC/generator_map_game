# editor/ui/bindings/project_bindings.py
import numpy as np
import logging

logger = logging.getLogger(__name__)


# Эта функция больше не нужна, но оставляем ее для совместимости, если где-то вызывается
def apply_project_to_ui(mw, data: dict) -> None:
    pass


def collect_context_from_ui(mw, for_preview: bool = True) -> dict:
    """
    Собирает контекст из UI и создает координатную сетку.
    Реализует логику "умного превью" с масштабированием.
    """
    try:
        # --- НАЧАЛО ИЗМЕНЕНИЙ: Получаем значения из новых полей ---
        # Разрешение берется из настроек превью или региона, в зависимости от цели
        if for_preview:
            preview_res_str = mw.preview_resolution_input.currentText()
            resolution = int(preview_res_str.split('x')[0])
        else:
            region_res_str = mw.region_resolution_input.currentText()
            resolution = int(region_res_str.split('x')[0])

        vertex_distance = mw.vertex_distance_input.value()
        max_height = mw.max_height_input.value()
        offset_x = mw.global_x_offset_input.value()
        offset_z = mw.global_z_offset_input.value()
        # --- КОНЕЦ ИЗМЕНЕНИЙ ---
    except (AttributeError, ValueError, IndexError) as e:
        logger.error(f"Ошибка чтения настроек из UI: {e}")
        # Значения по умолчанию в случае ошибки
        resolution = 512
        vertex_distance = 1.0
        max_height = 1000.0
        offset_x = 0.0
        offset_z = 0.0

    # --- НАЧАЛО ИЗМЕНЕНИЙ: Логика "умного превью" ---
    if for_preview:
        # Для превью мы симулируем, что расстояние между вершинами всегда 1 метр,
        # чтобы получить наглядное представление рельефа.
        preview_vertex_distance = 1.0

        # Пропорционально уменьшаем высоту, чтобы сохранить форму гор
        preview_max_height = max_height / vertex_distance if vertex_distance > 0 else max_height

        # Размер мира для превью рассчитывается на основе разрешения и "виртуального" расстояния
        world_size_meters = resolution * preview_vertex_distance

        # Сохраняем реальные значения в отдельный словарь для использования в нодах
        world_settings = {
            'resolution': resolution,
            'vertex_distance': vertex_distance,
            'max_height': max_height,
        }
    else:
        # Для финальной генерации используем реальные значения
        world_size_meters = resolution * vertex_distance
        preview_max_height = max_height
        world_settings = {
            'resolution': resolution,
            'vertex_distance': vertex_distance,
            'max_height': max_height,
        }
    # --- КОНЕЦ ИЗМЕНЕНИЙ ---

    logger.debug(
        f"Сборка контекста (превью={for_preview}): res={resolution}, world_size={world_size_meters}, max_h={preview_max_height}")

    half_size = world_size_meters / 2.0
    x_min, x_max = offset_x - half_size, offset_x + half_size
    z_min, z_max = offset_z - half_size, offset_z + half_size

    x_range = np.linspace(x_min, x_max, resolution, dtype=np.float32)
    z_range = np.linspace(z_min, z_max, resolution, dtype=np.float32)
    x_coords, z_coords = np.meshgrid(x_range, z_range)

    # Теперь передаем в контекст и "виртуальные" и реальные параметры
    return {
        "seed": 1337,  # Это значение все еще не используется, но оставим
        "x_coords": x_coords,
        "y_coords": np.zeros_like(x_coords),
        "z_coords": z_coords,
        "WORLD_SIZE_METERS": world_size_meters,
        "max_height_m": preview_max_height,  # <-- Высота для превью
        "world_settings": world_settings,  # <-- Реальные настройки для нод
    }
