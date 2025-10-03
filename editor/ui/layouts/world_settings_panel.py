# editor/ui/layouts/world_settings_panel.py
from __future__ import annotations
from PySide6 import QtWidgets

# --- ИЗМЕНЕНИЕ: Импортируем виджеты из их новых, правильных расположений ---

from editor.ui.widgets.custom_controls import SliderSpinCombo, SeedWidget, CollapsibleBox

# Таблица с данными о разделении сферы
SUBDIVISION_LEVELS = {
    "3 (92 регионов)": 92,
    "5 (252 регионов)": 252,
    "8 (642 регионов)": 642,
    "10 (1002 регионов)": 1002,
    "16 (2562 регионов)": 2562,
    "32 (10242 регионов)": 10242,
}


def make_world_settings_widget(main_window) -> tuple[QtWidgets.QWidget, dict]:
    """
    Фабричная функция, которая создает и настраивает панель настроек мира.
    """
    scroll_area = QtWidgets.QScrollArea()
    scroll_area.setWidgetResizable(True)
    scroll_area.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)

    root = QtWidgets.QWidget()
    scroll_area.setWidget(root)

    layout = QtWidgets.QVBoxLayout(root)
    layout.setContentsMargins(8, 8, 8, 8)
    layout.setSpacing(4)

    widgets = {}

    # --- Блок 1: Настройки планетарной сетки ---
    planetary_grid_box = CollapsibleBox("1. Планетарная сетка")
    planetary_grid_box.setChecked(True)

    widgets["subdivision_level_input"] = QtWidgets.QComboBox()
    widgets["subdivision_level_input"].addItems(SUBDIVISION_LEVELS.keys())
    widgets["subdivision_level_input"].setCurrentText("8 (642 регионов)")
    planetary_grid_box.body.addRow("Частота разделения:", widgets["subdivision_level_input"])

    layout.addWidget(planetary_grid_box)

    # --- Блок 2: Масштаб и Разрешение Региона ---
    world_scale_box = CollapsibleBox("2. Масштаб и Разрешение Региона")
    world_scale_box.setChecked(True)

    widgets["region_resolution_input"] = QtWidgets.QComboBox()
    widgets["region_resolution_input"].addItems(["512x512", "1024x1024", "2048x2048", "4096x4096"])
    widgets["region_resolution_input"].setCurrentText("1024x1024")
    world_scale_box.body.addRow("Разрешение региона (пикс):", widgets["region_resolution_input"])

    widgets["vertex_distance_input"] = QtWidgets.QDoubleSpinBox()
    widgets["vertex_distance_input"].setRange(0.1, 128.0)
    widgets["vertex_distance_input"].setValue(4.0)
    widgets["vertex_distance_input"].setDecimals(2)
    widgets["vertex_distance_input"].setSingleStep(0.5)
    world_scale_box.body.addRow("Расстояние м/вершина:", widgets["vertex_distance_input"])

    # Максимальная высота убрана из этого блока, так как она относится к генерации, а не к масштабу
    layout.addWidget(world_scale_box)

    # --- Блок 3: Координаты и Превью ---
    coords_box = CollapsibleBox("3. Координаты и Превью")
    coords_box.setChecked(True)

    widgets["global_x_offset_input"] = QtWidgets.QDoubleSpinBox()
    widgets["global_x_offset_input"].setRange(-10000000, 10000000)
    widgets["global_x_offset_input"].setSingleStep(1000)
    widgets["global_x_offset_input"].setDecimals(0)
    widgets["global_x_offset_input"].setValue(0)
    coords_box.body.addRow("Смещение X (м):", widgets["global_x_offset_input"])

    widgets["global_z_offset_input"] = QtWidgets.QDoubleSpinBox()
    widgets["global_z_offset_input"].setRange(-10000000, 10000000)
    widgets["global_z_offset_input"].setSingleStep(1000)
    widgets["global_z_offset_input"].setDecimals(0)
    widgets["global_z_offset_input"].setValue(0)
    coords_box.body.addRow("Смещение Z (м):", widgets["global_z_offset_input"])

    coords_box.body.addRow(QtWidgets.QLabel("---"))  # Разделитель

    widgets["realtime_checkbox"] = QtWidgets.QCheckBox("Обновлять в реальном времени")
    widgets["realtime_checkbox"].setChecked(True)
    coords_box.body.addRow(widgets["realtime_checkbox"])
    layout.addWidget(coords_box)

    # --- Блок 4: Глобальный Шум (Планета) ---
    ws_noise_box = CollapsibleBox("4. Глобальный Шум (Планета)")
    ws_noise_box.setChecked(True)

    # Максимальная высота теперь здесь, так как она напрямую влияет на амплитуду шума
    widgets["max_height_input"] = QtWidgets.QDoubleSpinBox()
    widgets["max_height_input"].setRange(1.0, 50000.0)
    widgets["max_height_input"].setValue(4000.0)
    widgets["max_height_input"].setDecimals(0)
    ws_noise_box.body.addRow("Макс. Высота (м):", widgets["max_height_input"])

    ws_noise_box.body.addRow(QtWidgets.QLabel("---"))  # Разделитель

    # Полярные океаны
    ocean_group = QtWidgets.QGroupBox("Полярные Океаны")
    ocean_form = QtWidgets.QFormLayout(ocean_group)
    widgets["ws_ocean_enabled"] = QtWidgets.QCheckBox("Включить")
    widgets["ws_ocean_enabled"].setChecked(False)  # Отключены по умолчанию, как вы и хотели
    ocean_form.addRow(widgets["ws_ocean_enabled"])

    widgets["ws_ocean_latitude"] = SliderSpinCombo()
    widgets["ws_ocean_latitude"].setRange(0.0, 90.0)
    widgets["ws_ocean_latitude"].setValue(75.0)
    ocean_form.addRow("Начало океана (°):", widgets["ws_ocean_latitude"])

    widgets["ws_ocean_falloff"] = SliderSpinCombo()
    widgets["ws_ocean_falloff"].setRange(0.0, 45.0)
    widgets["ws_ocean_falloff"].setValue(10.0)
    ocean_form.addRow("Плавность перехода (°):", widgets["ws_ocean_falloff"])
    ws_noise_box.body.addRow(ocean_group)

    # Настройки шума
    fbm_group = QtWidgets.QGroupBox("Настройки шума")
    fbm_form = QtWidgets.QFormLayout(fbm_group)
    widgets["ws_sphere_frequency"] = SliderSpinCombo()
    widgets["ws_sphere_frequency"].setRange(0.1, 64.0)
    widgets["ws_sphere_frequency"].setValue(4.0)
    fbm_form.addRow("Частота:", widgets["ws_sphere_frequency"])
    # ... (остальные настройки шума без изменений) ...
    widgets["ws_sphere_octaves"] = SliderSpinCombo()
    fbm_form.addRow("Октавы:", widgets["ws_sphere_octaves"])
    widgets["ws_sphere_gain"] = SliderSpinCombo()
    fbm_form.addRow("Gain (Roughness):", widgets["ws_sphere_gain"])
    widgets["ws_sphere_ridge"] = QtWidgets.QCheckBox("Гребни (Ridged)")
    fbm_form.addRow(widgets["ws_sphere_ridge"])
    widgets["ws_sphere_seed"] = SeedWidget()
    fbm_form.addRow("Seed:", widgets["ws_sphere_seed"])
    ws_noise_box.body.addRow(fbm_group)

    layout.addWidget(ws_noise_box)
    layout.addStretch()

    widgets["ws_noise_box"] = ws_noise_box

    return scroll_area, widgets