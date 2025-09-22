# ==============================================================================
# Файл: editor/ui_panels/project_params_panel.py
# Назначение: Модуль для создания панели "Параметры Проекта".
# ВЕРСИЯ 1.1: Исправлен импорт QtCore.
# ==============================================================================
from PySide6 import QtWidgets, QtCore  # <-- ДОБАВЛЕН ИМПОРТ QtCore


def create_project_params_dock(main_window) -> None:
    """
    Создает и настраивает док-виджет с основными параметрами проекта.
    """
    settings_widget = QtWidgets.QWidget()
    form_layout = QtWidgets.QFormLayout(settings_widget)

    main_window.seed_input = QtWidgets.QSpinBox(minimum=0, maximum=999999)
    form_layout.addRow("World Seed:", main_window.seed_input)

    main_window.global_x_offset_input = QtWidgets.QSpinBox(minimum=-999999, maximum=999999, singleStep=512)
    form_layout.addRow("Global X Offset:", main_window.global_x_offset_input)

    main_window.global_z_offset_input = QtWidgets.QSpinBox(minimum=-999999, maximum=999999, singleStep=512)
    form_layout.addRow("Global Z Offset:", main_window.global_z_offset_input)

    main_window.chunk_size_input = QtWidgets.QSpinBox(minimum=64, maximum=1024)
    form_layout.addRow("Chunk Size (px):", main_window.chunk_size_input)

    main_window.region_size_input = QtWidgets.QSpinBox(minimum=1, maximum=32)
    form_layout.addRow("Region Size (chunks):", main_window.region_size_input)

    main_window.cell_size_input = QtWidgets.QDoubleSpinBox(minimum=0.1, maximum=10.0, decimals=2, singleStep=0.1)
    form_layout.addRow("Cell Size (m):", main_window.cell_size_input)

    dock = QtWidgets.QDockWidget("Параметры Проекта", main_window)
    dock.setWidget(settings_widget)

    # --- ИСПРАВЛЕНИЕ: Используем QtCore.Qt вместо QtWidgets.Qt ---
    main_window.addDockWidget(QtCore.Qt.DockWidgetArea.RightDockWidgetArea, dock)