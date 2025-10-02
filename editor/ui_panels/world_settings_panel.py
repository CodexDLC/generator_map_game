# editor/ui_panels/world_settings_panel.py
from __future__ import annotations
from PySide6 import QtWidgets, QtCore
from editor.ui_panels.accordion_properties import CollapsibleBox, SliderSpinCombo, SeedWidget


def make_world_settings_widget(main_window) -> tuple[QtWidgets.QWidget, dict]:
    scroll_area = QtWidgets.QScrollArea()
    scroll_area.setWidgetResizable(True)
    scroll_area.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)

    root = QtWidgets.QWidget()
    scroll_area.setWidget(root)

    layout = QtWidgets.QVBoxLayout(root)
    layout.setContentsMargins(8, 8, 8, 8)
    layout.setSpacing(4)

    widgets = {}

    world_scale_box = CollapsibleBox("1. Масштаб и Координаты")
    world_scale_box.setChecked(True)

    widgets["global_x_offset_input"] = QtWidgets.QDoubleSpinBox()
    widgets["global_x_offset_input"].setRange(-1000000, 1000000)
    widgets["global_x_offset_input"].setSingleStep(1000)
    widgets["global_x_offset_input"].setDecimals(0)
    widgets["global_x_offset_input"].setValue(0)
    world_scale_box.body.addRow("Смещение X (м):", widgets["global_x_offset_input"])

    widgets["global_z_offset_input"] = QtWidgets.QDoubleSpinBox()
    widgets["global_z_offset_input"].setRange(-1000000, 1000000)
    widgets["global_z_offset_input"].setSingleStep(1000)
    widgets["global_z_offset_input"].setDecimals(0)
    widgets["global_z_offset_input"].setValue(0)
    world_scale_box.body.addRow("Смещение Z (м):", widgets["global_z_offset_input"])

    world_scale_box.body.addRow(QtWidgets.QLabel("---"))

    widgets["world_size_input"] = QtWidgets.QDoubleSpinBox()
    widgets["world_size_input"].setRange(256.0, 65536.0)
    widgets["world_size_input"].setValue(5000.0)
    widgets["world_size_input"].setSingleStep(100)
    widgets["world_size_input"].setDecimals(0)
    world_scale_box.body.addRow("Размер Мира (м):", widgets["world_size_input"])

    widgets["max_height_input"] = QtWidgets.QDoubleSpinBox()
    widgets["max_height_input"].setRange(1.0, 50000.0)
    widgets["max_height_input"].setValue(1200.0)
    world_scale_box.body.addRow("Макс. Высота (м):", widgets["max_height_input"])

    widgets["vertex_spacing_input"] = QtWidgets.QDoubleSpinBox()
    widgets["vertex_spacing_input"].setRange(0.1, 100.0)
    widgets["vertex_spacing_input"].setValue(1.0)
    world_scale_box.body.addRow("Масштаб X/Z (м/пиксель):", widgets["vertex_spacing_input"])

    layout.addWidget(world_scale_box)

    preview_box = CollapsibleBox("2. Рендер Превью")
    preview_box.setChecked(True)
    widgets["resolution_input"] = QtWidgets.QComboBox()
    widgets["resolution_input"].addItems(["256x256", "512x512", "1024x1024", "2048x2048"])
    widgets["resolution_input"].setCurrentText("1024x1024")
    preview_box.body.addRow("Разрешение:", widgets["resolution_input"])
    widgets["realtime_checkbox"] = QtWidgets.QCheckBox("Обновлять в реальном времени")
    widgets["realtime_checkbox"].setChecked(True)
    preview_box.body.addRow(widgets["realtime_checkbox"])
    layout.addWidget(preview_box)

    ws_noise_box = CollapsibleBox("3. Глобальный Шум (Цилиндрический)")
    ws_noise_box.setChecked(True)
    noise_layout = ws_noise_box.body

    ocean_group = QtWidgets.QGroupBox("Полярные Океаны")
    ocean_form = QtWidgets.QFormLayout(ocean_group)

    widgets["ws_ocean_latitude"] = SliderSpinCombo()
    widgets["ws_ocean_latitude"].setRange(0.0, 90.0)
    widgets["ws_ocean_latitude"].setValue(75.0)
    widgets["ws_ocean_latitude"].setDecimals(1)
    ocean_form.addRow("Начало океана (°):", widgets["ws_ocean_latitude"])

    widgets["ws_ocean_falloff"] = SliderSpinCombo()
    widgets["ws_ocean_falloff"].setRange(0.0, 45.0)
    widgets["ws_ocean_falloff"].setValue(10.0)
    widgets["ws_ocean_falloff"].setDecimals(1)
    ocean_form.addRow("Плавность перехода (°):", widgets["ws_ocean_falloff"])
    
    noise_layout.addRow(ocean_group)

    fbm_group = QtWidgets.QGroupBox("Настройки шума")
    fbm_form = QtWidgets.QFormLayout(fbm_group)

    widgets["ws_sphere_frequency"] = SliderSpinCombo()
    widgets["ws_sphere_frequency"].setRange(0.1, 64.0)
    widgets["ws_sphere_frequency"].setValue(4.0)
    fbm_form.addRow("Частота:", widgets["ws_sphere_frequency"])

    widgets["ws_sphere_octaves"] = SliderSpinCombo()
    widgets["ws_sphere_octaves"].setRange(1, 16)
    widgets["ws_sphere_octaves"].setValue(8)
    widgets["ws_sphere_octaves"].setDecimals(0)
    fbm_form.addRow("Октавы:", widgets["ws_sphere_octaves"])

    widgets["ws_sphere_gain"] = SliderSpinCombo()
    widgets["ws_sphere_gain"].setRange(0.0, 1.0)
    widgets["ws_sphere_gain"].setValue(0.5)
    fbm_form.addRow("Gain (Roughness):", widgets["ws_sphere_gain"])

    widgets["ws_sphere_ridge"] = QtWidgets.QCheckBox("Гребни (Ridged)")
    fbm_form.addRow(widgets["ws_sphere_ridge"])

    widgets["ws_sphere_seed"] = SeedWidget()
    widgets["ws_sphere_seed"].setValue(0)
    fbm_form.addRow("Seed:", widgets["ws_sphere_seed"])

    noise_layout.addRow(fbm_group)

    warp_group = QtWidgets.QGroupBox("Warp")
    warp_form = QtWidgets.QFormLayout(warp_group)
    widgets["ws_warp_type"] = QtWidgets.QComboBox()
    widgets["ws_warp_type"].addItems(["None", "Simple", "Complex"])
    warp_form.addRow("Type:", widgets["ws_warp_type"])

    widgets["ws_warp_rel_size"] = SliderSpinCombo()
    widgets["ws_warp_rel_size"].setRange(0.05, 8.0)
    widgets["ws_warp_rel_size"].setValue(1.0)
    widgets["ws_warp_rel_size"].setDecimals(3)
    warp_form.addRow("Relative Size:", widgets["ws_warp_rel_size"])

    widgets["ws_warp_strength"] = SliderSpinCombo()
    widgets["ws_warp_strength"].setRange(0.0, 1.0)
    widgets["ws_warp_strength"].setValue(0.5)
    widgets["ws_warp_strength"].setDecimals(3)
    warp_form.addRow("Strength:", widgets["ws_warp_strength"])

    noise_layout.addRow(warp_group)

    layout.addWidget(ws_noise_box)
    layout.addStretch()

    widgets["ws_noise_box"] = ws_noise_box

    return scroll_area, widgets
