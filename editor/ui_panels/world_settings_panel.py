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

def make_world_settings_widget(main_window) -> QtWidgets.QWidget:
    root = QtWidgets.QWidget()
    layout = QtWidgets.QVBoxLayout(root)
    layout.setContentsMargins(8, 8, 8, 8)

    # --- Секция 1: Масштаб Мира ---
    world_scale_box = _create_group_box("1. Масштаб Мира")
    form1 = world_scale_box.layout()

    main_window.ws_max_height_input = QtWidgets.QDoubleSpinBox()
    main_window.ws_max_height_input.setRange(1.0, 50000.0)
    main_window.ws_max_height_input.setValue(1200.0)
    form1.addRow("Макс. Высота (м):", main_window.ws_max_height_input)

    main_window.ws_vertex_spacing_input = QtWidgets.QDoubleSpinBox()
    main_window.ws_vertex_spacing_input.setRange(0.1, 100.0)
    main_window.ws_vertex_spacing_input.setValue(1.0)
    form1.addRow("Масштаб X/Z (м/пиксель):", main_window.ws_vertex_spacing_input)

    layout.addWidget(world_scale_box)

    # --- Секция 2: Рендер Превью ---
    preview_box = _create_group_box("2. Рендер Превью")
    form2 = preview_box.layout()

    main_window.pv_resolution_input = QtWidgets.QComboBox()
    main_window.pv_resolution_input.addItems(["256x256", "512x512", "1024x1024", "2048x2048"])
    main_window.pv_resolution_input.setCurrentText("1024x1024")
    form2.addRow("Разрешение:", main_window.pv_resolution_input)

    main_window.pv_realtime_checkbox = QtWidgets.QCheckBox("Обновлять в реальном времени")
    main_window.pv_realtime_checkbox.setChecked(True)
    form2.addRow(main_window.pv_realtime_checkbox)

    layout.addWidget(preview_box)

    # --- ИЗМЕНЕНИЕ: Секция 3 теперь "Мировой Фрактал" ---
    variation_box = _create_group_box("3. Мировой Фрактал")
    form3 = variation_box.layout()

    main_window.gv_scale_input = QtWidgets.QDoubleSpinBox()
    main_window.gv_scale_input.setRange(0.001, 10.0); main_window.gv_scale_input.setDecimals(3)
    main_window.gv_scale_input.setValue(0.5)
    form3.addRow("Масштаб:", main_window.gv_scale_input)

    main_window.gv_octaves_input = QtWidgets.QSpinBox()
    main_window.gv_octaves_input.setRange(1, 16); main_window.gv_octaves_input.setValue(8)
    form3.addRow("Октавы:", main_window.gv_octaves_input)

    main_window.gv_roughness_input = QtWidgets.QDoubleSpinBox()
    main_window.gv_roughness_input.setRange(0.0, 1.0); main_window.gv_roughness_input.setDecimals(2)
    main_window.gv_roughness_input.setValue(0.5)
    form3.addRow("Шершавость:", main_window.gv_roughness_input)

    main_window.gv_variation_input = QtWidgets.QDoubleSpinBox()
    main_window.gv_variation_input.setRange(0.0, 10.0); main_window.gv_variation_input.setDecimals(2)
    main_window.gv_variation_input.setValue(2.0)
    form3.addRow("Сила вариации:", main_window.gv_variation_input)

    layout.addWidget(variation_box)
    layout.addStretch()
    return root
