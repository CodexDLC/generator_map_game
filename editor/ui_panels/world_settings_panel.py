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

    ws_noise_box = CollapsibleBox("3. Глобальный Шум (World Input)")
    ws_noise_box.setChecked(True)

    noise_layout = QtWidgets.QVBoxLayout()
    ws_noise_box.body.addRow(noise_layout)

    fractal_group = QtWidgets.QGroupBox("Fractal")
    fractal_form = QtWidgets.QFormLayout(fractal_group)
    widgets["ws_fractal_type"] = QtWidgets.QComboBox()
    widgets["ws_fractal_type"].addItems(["FBM", "Ridged", "Billowy"])
    fractal_form.addRow("Type:", widgets["ws_fractal_type"])

    # --- ИЗМЕНЕНИЕ: Создаем виджет по умолчанию (slider_on_left=True) ---
    widgets["ws_fractal_scale"] = SliderSpinCombo()
    widgets["ws_fractal_scale"].setRange(1.0, 500.0)
    widgets["ws_fractal_scale"].setValue(100.0)
    widgets["ws_fractal_scale"].setDecimals(2)
    fractal_form.addRow("Scale (%):", widgets["ws_fractal_scale"])

    widgets["ws_fractal_octaves"] = SliderSpinCombo()
    widgets["ws_fractal_octaves"].setRange(1, 16)
    widgets["ws_fractal_octaves"].setValue(8)
    widgets["ws_fractal_octaves"].setDecimals(0)
    fractal_form.addRow("Octaves:", widgets["ws_fractal_octaves"])

    widgets["ws_fractal_roughness"] = SliderSpinCombo()
    widgets["ws_fractal_roughness"].setRange(0.0, 1.0)
    widgets["ws_fractal_roughness"].setValue(0.5)
    widgets["ws_fractal_roughness"].setDecimals(3)
    fractal_form.addRow("Roughness:", widgets["ws_fractal_roughness"])

    widgets["ws_fractal_seed"] = SeedWidget()
    widgets["ws_fractal_seed"].setValue(0)
    fractal_form.addRow("Seed:", widgets["ws_fractal_seed"])
    noise_layout.addWidget(fractal_group)

    var_group = QtWidgets.QGroupBox("Variation")
    var_form = QtWidgets.QFormLayout(var_group)
    widgets["ws_var_strength"] = SliderSpinCombo()
    widgets["ws_var_strength"].setRange(0.0, 4.0)
    widgets["ws_var_strength"].setValue(1.0)
    widgets["ws_var_strength"].setDecimals(3)
    var_form.addRow("Variation:", widgets["ws_var_strength"])

    widgets["ws_var_smoothness"] = SliderSpinCombo()
    widgets["ws_var_smoothness"].setRange(-20.0, 20.0)
    widgets["ws_var_smoothness"].setValue(0.0)
    widgets["ws_var_smoothness"].setDecimals(3)
    var_form.addRow("Smoothness:", widgets["ws_var_smoothness"])

    widgets["ws_var_contrast"] = SliderSpinCombo()
    widgets["ws_var_contrast"].setRange(0.0, 1.0)
    widgets["ws_var_contrast"].setValue(0.3)
    widgets["ws_var_contrast"].setDecimals(3)
    var_form.addRow("Contrast:", widgets["ws_var_contrast"])

    widgets["ws_var_damping"] = SliderSpinCombo()
    widgets["ws_var_damping"].setRange(0.0, 1.0)
    widgets["ws_var_damping"].setValue(0.25)
    widgets["ws_var_damping"].setDecimals(3)
    var_form.addRow("Damping:", widgets["ws_var_damping"])

    widgets["ws_var_bias"] = SliderSpinCombo()
    widgets["ws_var_bias"].setRange(0.0, 1.0)
    widgets["ws_var_bias"].setValue(0.5)
    widgets["ws_var_bias"].setDecimals(3)
    var_form.addRow("Bias:", widgets["ws_var_bias"])

    noise_layout.addWidget(var_group)

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

    noise_layout.addWidget(warp_group)

    layout.addWidget(ws_noise_box)
    layout.addStretch()

    widgets["ws_noise_box"] = ws_noise_box

    return scroll_area, widgets