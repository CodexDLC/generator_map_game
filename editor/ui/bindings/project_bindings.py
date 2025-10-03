# editor/ui/bindings/project_bindings.py
import numpy as np
import logging

logger = logging.getLogger(__name__)

def apply_project_to_ui(mw, data: dict) -> None:
    pass # Эта функция больше не нужна

def collect_context_from_ui(mw, for_preview: bool = True) -> dict:
    """
    Собирает контекст из UI, используя сохраненное смещение от клика по карте.
    """
    try:
        if for_preview:
            preview_res_str = mw.preview_resolution_input.currentText()
            resolution = int(preview_res_str.split('x')[0])
        else:
            region_res_str = mw.region_resolution_input.currentText()
            resolution = int(region_res_str.split('x')[0])

        vertex_distance = mw.vertex_distance_input.value()
        max_height = mw.max_height_input.value()
        
        # --- ИЗМЕНЕНИЕ: Берем смещение из сохраненного состояния, а не из UI ---
        offset_x, offset_z = mw.current_world_offset
        # --- КОНЕЦ ИЗМЕНЕНИЯ ---
        
    except (AttributeError, ValueError, IndexError) as e:
        logger.error(f"Ошибка чтения настроек из UI: {e}")
        resolution, vertex_distance, max_height = 512, 1.0, 1000.0
        offset_x, offset_z = 0.0, 0.0

    # Логика "умного превью" остается без изменений
    if for_preview:
        preview_vertex_distance = 1.0
        preview_max_height = max_height / vertex_distance if vertex_distance > 0 else max_height
        world_size_meters = resolution * preview_vertex_distance
    else:
        world_size_meters = resolution * vertex_distance
        preview_max_height = max_height

    half_size = world_size_meters / 2.0
    x_min, x_max = offset_x - half_size, offset_x + half_size
    z_min, z_max = offset_z - half_size, offset_z + half_size

    x_range = np.linspace(x_min, x_max, resolution, dtype=np.float32)
    z_range = np.linspace(z_min, z_max, resolution, dtype=np.float32)
    x_coords, z_coords = np.meshgrid(x_range, z_range)

    return {
        "x_coords": x_coords,
        "z_coords": z_coords,
        "WORLD_SIZE_METERS": world_size_meters,
        "max_height_m": preview_max_height,
        # ... остальные поля контекста
    }
