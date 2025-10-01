# editor/ui_panels/world_settings_panel.py
from __future__ import annotations
from PySide6 import QtWidgets, QtCore


def _create_group_box(title: str) -> QtWidgets.QGroupBox:
    box = QtWidgets.QGroupBox(title)
    box.setCheckable(True)
    layout = QtWidgets.QFormLayout(box)
    layout.setContentsMargins(8, 20, 8, 8)
    layout.setSpacing(6)
    return box


def make_world_settings_widget(main_window) -> tuple[QtWidgets.QWidget, dict]:
    root = QtWidgets.QWidget()
    layout = QtWidgets.QVBoxLayout(root)
    layout.setContentsMargins(8, 8, 8, 8)

    widgets = {}

    # --- Секция 1: Масштаб Мира ---
    world_scale_box = _create_group_box("1. Масштаб Мира")
    form1 = world_scale_box.layout()

    # --- НАЧАЛО ИЗМЕНЕНИЯ ---

    # Поле для смещения по X
    widgets["global_x_offset_input"] = QtWidgets.QDoubleSpinBox()
    widgets["global_x_offset_input"].setRange(-1000000, 1000000)
    widgets["global_x_offset_input"].setSingleStep(1000)
    widgets["global_x_offset_input"].setDecimals(0)
    widgets["global_x_offset_input"].setValue(0)
    form1.addRow("Global Offset X (m):", widgets["global_x_offset_input"])

    # Поле для смещения по Z
    widgets["global_z_offset_input"] = QtWidgets.QDoubleSpinBox()
    widgets["global_z_offset_input"].setRange(-1000000, 1000000)
    widgets["global_z_offset_input"].setSingleStep(1000)
    widgets["global_z_offset_input"].setDecimals(0)
    widgets["global_z_offset_input"].setValue(0)
    form1.addRow("Global Offset Z (m):", widgets["global_z_offset_input"])

    form1.addRow(QtWidgets.QLabel("---"))  # Разделитель

    # --- КОНЕЦ ИЗМЕНЕНИЯ ---

    widgets["world_size_input"] = QtWidgets.QDoubleSpinBox()
    widgets["world_size_input"].setRange(256.0, 65536.0)
    widgets["world_size_input"].setValue(5000.0)
    widgets["world_size_input"].setSingleStep(100)
    widgets["world_size_input"].setDecimals(0)
    form1.addRow("Размер Мира (м):", widgets["world_size_input"])

    widgets["max_height_input"] = QtWidgets.QDoubleSpinBox()
    widgets["max_height_input"].setRange(1.0, 50000.0)
    widgets["max_height_input"].setValue(1200.0)
    form1.addRow("Макс. Высота (м):", widgets["max_height_input"])

    widgets["vertex_spacing_input"] = QtWidgets.QDoubleSpinBox()
    widgets["vertex_spacing_input"].setRange(0.1, 100.0)
    widgets["vertex_spacing_input"].setValue(1.0)
    form1.addRow("Масштаб X/Z (м/пиксель):", widgets["vertex_spacing_input"])

    layout.addWidget(world_scale_box)

    # ... (остальной код файла без изменений) ...

    # --- Секция 2: Рендер Превью ---
    preview_box = _create_group_box("2. Рендер Превью")
    form2 = preview_box.layout()

    widgets["resolution_input"] = QtWidgets.QComboBox()
    widgets["resolution_input"].addItems(["256x256", "512x512", "1024x1024", "2048x2048"])
    widgets["resolution_input"].setCurrentText("1024x1024")
    form2.addRow("Разрешение:", widgets["resolution_input"])

    widgets["realtime_checkbox"] = QtWidgets.QCheckBox("Обновлять в реальном времени")
    widgets["realtime_checkbox"].setChecked(True)
    form2.addRow(widgets["realtime_checkbox"])

    layout.addWidget(preview_box)

    # --- Секция 3: Глобальный Шум ---
    variation_box = _create_group_box("3. Глобальный Шум")
    form3 = variation_box.layout()

    widgets["gv_scale_input"] = QtWidgets.QDoubleSpinBox()
    widgets["gv_scale_input"].setRange(0.01, 10.0)
    widgets["gv_scale_input"].setSingleStep(0.1)
    widgets["gv_scale_input"].setDecimals(2)
    widgets["gv_scale_input"].setValue(1.0)
    form3.addRow("Масштаб (%):", widgets["gv_scale_input"])

    widgets["gv_octaves_input"] = QtWidgets.QSpinBox()
    widgets["gv_octaves_input"].setRange(1, 16)
    widgets["gv_octaves_input"].setValue(4)
    form3.addRow("Октавы:", widgets["gv_octaves_input"])

    widgets["gv_strength_input"] = QtWidgets.QDoubleSpinBox()
    widgets["gv_strength_input"].setRange(0.0, 1.0)
    widgets["gv_strength_input"].setDecimals(2)
    widgets["gv_strength_input"].setValue(0.5)
    form3.addRow("Сила (0-1):", widgets["gv_strength_input"])

    layout.addWidget(variation_box)
    layout.addStretch()

    return root, widgets