# editor/ui_panels/project_binding.py
import numpy as np

# Старая функция apply_project_to_ui больше не актуальна,
# так как все UI элементы изменились. Оставляем ее пустой.
def apply_project_to_ui(mw, data: dict) -> None:
    pass

def collect_context_from_ui(mw) -> dict:
    """
    Собирает базовый контекст и создает координатную сетку для превью.
    """
    try:
        resolution_str = mw.pv_resolution_input.currentText()
        preview_res = int(resolution_str.split('x')[0])
    except (AttributeError, ValueError, IndexError):
        preview_res = 1024 # Fallback

    # Создаем координатную сетку от -1 до 1
    x = np.linspace(-1.0, 1.0, preview_res, dtype=np.float32)
    y = np.linspace(-1.0, 1.0, preview_res, dtype=np.float32)
    x_coords, y_coords = np.meshgrid(x, y)
    z_coords = np.zeros_like(x_coords, dtype=np.float32)

    # ВАЖНО: В новом UI отсутствует поле для ввода глобального сида.
    # Временно используем константу, чтобы избежать падения.
    seed = 1337

    return {
        "seed": seed,
        "x_coords": x_coords,
        "y_coords": y_coords,
        "z_coords": z_coords,
    }
