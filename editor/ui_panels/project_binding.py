# editor/ui_panels/project_binding.py
import numpy as np


# Эта функция больше не нужна, но оставляем ее для совместимости, если где-то вызывается
def apply_project_to_ui(mw, data: dict) -> None:
    pass


def collect_context_from_ui(mw) -> dict:
    """
    Собирает контекст из UI и создает координатную сетку в мировом пространстве.
    """
    try:
        resolution_str = mw.pv_resolution_input.currentText()
        preview_res = int(resolution_str.split('x')[0])
    except (AttributeError, ValueError, IndexError):
        preview_res = 1024  # Fallback

    # --- КОНЦЕПТУАЛЬНОЕ ИЗМЕНЕНИЕ ---

    # 1. Получаем размер мира из нового поля в UI
    try:
        world_size_meters = mw.ws_world_size_input.value()
    except AttributeError:
        world_size_meters = 5000.0  # Запасной вариант

    # 2. Получаем смещения
    try:
        offset_x = mw.global_x_offset_input.value()
        offset_z = mw.global_z_offset_input.value()
    except AttributeError:
        offset_x = 0.0
        offset_z = 0.0

    # 3. Рассчитываем границы видимой области
    half_size = world_size_meters / 2.0
    x_min, x_max = offset_x - half_size, offset_x + half_size
    z_min, z_max = offset_z - half_size, offset_z + half_size

    # 4. Создаем сетку мировых координат
    x_range = np.linspace(x_min, x_max, preview_res, dtype=np.float32)
    z_range = np.linspace(z_min, z_max, preview_res, dtype=np.float32)
    x_coords, z_coords = np.meshgrid(x_range, z_range)

    seed = 1337

    return {
        "seed": seed,
        "x_coords": x_coords,
        "y_coords": np.zeros_like(x_coords),
        "z_coords": z_coords,
        "WORLD_SIZE_METERS": world_size_meters,  # <--- Передаем в контекст
    }