# ==============================================================================
# Файл: editor/ui_panels/project_params_panel.py
# Назначение: Модуль для создания панели "Параметры Проекта".
# ВЕРСИЯ 1.2: Добавлен objectName.
# ==============================================================================
from PySide6 import QtWidgets, QtCore

from editor.system_utils import get_recommended_max_map_size


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

    form_layout.addRow(QtWidgets.QLabel("---"))

    main_window.total_size_label = QtWidgets.QLabel("Total size: 0 x 0 px")
    main_window.total_size_label.setStyleSheet("color: #aaa;")
    form_layout.addRow(main_window.total_size_label)

    recommended_size = get_recommended_max_map_size()
    rec_label = QtWidgets.QLabel(f"Recommended max: {recommended_size} px")
    rec_label.setStyleSheet("color: #88aaff;")
    form_layout.addRow(rec_label)

    def update_total_size():
        cs = main_window.chunk_size_input.value()
        rs = main_window.region_size_input.value()
        total = cs * rs
        main_window.total_size_label.setText(f"Total size: {total} x {total} px")

        if total > recommended_size:
            main_window.total_size_label.setStyleSheet("color: #ffcc00; font-weight: bold;")
        else:
            main_window.total_size_label.setStyleSheet("color: #aaa;")

    main_window.chunk_size_input.valueChanged.connect(update_total_size)
    main_window.region_size_input.valueChanged.connect(update_total_size)

    dock = QtWidgets.QDockWidget("Параметры Проекта", main_window)
    dock.setObjectName("Панель 'Параметры Проекта'")
    dock.setWidget(settings_widget)

    main_window.addDockWidget(QtCore.Qt.DockWidgetArea.RightDockWidgetArea, dock)

    main_window.dock_project_params = dock
