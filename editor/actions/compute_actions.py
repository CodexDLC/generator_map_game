# ==============================================================================
# Файл: editor/actions/compute_actions.py
# ВЕРСИЯ 2.0: Добавлена поддержка глобальных координат.
# ==============================================================================
import numpy as np
from ..graph_runner import compute_graph


def on_apply_clicked(main_window):
    """
    Собирает все необходимые данные из UI, формирует контекст
    и запускает вычисление графа для 3D-предпросмотра.
    """
    print("\n[Action] === APPLY CLICKED ===")
    main_window.statusBar.showMessage("Вычисление графа...")

    # 1. Собираем все настройки из UI
    chunk_size = main_window.chunk_size_input.value()
    region_size = main_window.region_size_input.value()
    preview_size = chunk_size * region_size

    cell_size = main_window.cell_size_input.value()
    world_seed = main_window.seed_input.value()
    global_x_offset = main_window.global_x_offset_input.value()
    global_z_offset = main_window.global_z_offset_input.value()

    # --- НАЧАЛО КЛЮЧЕВЫХ ИЗМЕНЕНИЙ ---
    # 2. Создаем сетку координат с учетом глобального смещения
    # Теперь мы генерируем не от 0, а от global_offset
    px_coords_x = np.arange(preview_size, dtype=np.float32) + global_x_offset
    px_coords_z = np.arange(preview_size, dtype=np.float32) + global_z_offset
    x_coords, z_coords = np.meshgrid(px_coords_x, px_coords_z)

    # 3. Формируем "контекст", который будет доступен всем нодам
    context = {
        "main_heightmap": np.zeros((preview_size, preview_size), dtype=np.float32),
        "x_coords": x_coords,
        "z_coords": z_coords,
        "cell_size": cell_size,
        "seed": world_seed,
        "global_x_offset": global_x_offset,
        "global_z_offset": global_z_offset,
        "chunk_size": chunk_size,
        "region_size_in_chunks": region_size
    }
    # --- КОНЕЦ КЛЮЧЕВЫХ ИЗМЕНЕНИЙ ---

    # 4. Запускаем "исполнителя" графа
    result_map, message = compute_graph(main_window.graph, context)

    # 5. Обновляем UI результатами
    main_window.statusBar.showMessage(message)
    if result_map is not None:
        print(f"Результат получен! Средняя высота: {result_map.mean():.2f}")
        main_window.preview_widget.update_mesh(result_map, cell_size)
    else:
        print(f"Вычисление не удалось.")