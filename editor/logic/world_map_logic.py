# editor/logic/world_map_logic.py
import logging
import numpy as np

logger = logging.getLogger(__name__)

def calculate_offset_from_map_click(
    u: float, v: float, layout_info: dict,
    region_res_str: str, vertex_distance: float
) -> tuple[float, float]:
    """
    Рассчитывает мировое смещение (в метрах) по клику на карте.
    """
    if not layout_info or 'layout' not in layout_info:
        return 0.0, 0.0

    layout = layout_info.get("layout", {})
    
    # Параметры из UI для расчета масштаба
    try:
        resolution = int(region_res_str.split('x')[0])
    except:
        resolution = 1024
    
    region_size_meters = resolution * vertex_distance

    # Координаты клика в пикселях холста
    canvas_width = layout_info.get("canvas_width_px", 1)
    canvas_height = layout_info.get("canvas_height_px", 1)
    clicked_px = u * canvas_width
    clicked_py = v * canvas_height

    # Ищем ближайший гекс
    closest_id = -1
    min_dist_sq = float('inf')
    
    for region_id, (px, py) in layout_info.get("pixel_positions", {}).items():
        dist_sq = (clicked_px - px)**2 + (clicked_py - py)**2
        if dist_sq < min_dist_sq:
            min_dist_sq = dist_sq
            closest_id = region_id

    if closest_id == -1:
        return 0.0, 0.0

    logger.info(f"Клик по региону ID: {closest_id}")

    # Получаем нормализованные 2D-координаты центра выбранного гекса
    norm_x, norm_y = layout.get(closest_id, (0.5, 0.5))

    # Преобразуем их в мировые координаты (приблизительно)
    # Предполагаем, что вся карта мира укладывается в некий большой квадрат
    total_world_width = region_size_meters * layout_info.get("layout_width_in_regions", 10)
    total_world_height = region_size_meters * layout_info.get("layout_height_in_regions", 6)

    offset_x = (norm_x - 0.5) * total_world_width
    offset_z = (norm_y - 0.5) * total_world_height * -1 # Ось Z инвертирована

    return offset_x, offset_z