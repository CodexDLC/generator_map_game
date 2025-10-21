# editor/ui/layouts/world_settings_panel.py
from __future__ import annotations
from PySide6 import QtWidgets

from editor.ui.widgets.custom_controls import CollapsibleBox, SliderSpinCombo, SeedWidget

SUBDIVISION_LEVELS = {
    "3 (92 регионов)": 92, "5 (252 регионов)": 252, "8 (642 регионов)": 642,
    "10 (1002 регионов)": 1002, "16 (2562 регионов)": 2562, "32 (10242 регионов)": 10242,
}
ALLOWED_RESOLUTIONS = ["1024x1024", "2048x2048", "4096x4096"]
MAX_SIDE_METERS = 65536.0

PLANET_ROUGHNESS_PRESETS = {
    "Газовый гигант (0.01%)": (0.0001, 2.5),
    "Луна/Меркурий (0.1%)": (0.001, 2.5),
    "Землеподобная (0.3%)": (0.003, 2.5),
    "Скалистый астероид (1.2%)": (0.012, 2.0),
    "Фэнтези-мир (2.5%)": (0.025, 1.8),
}


def make_world_settings_widget(main_window) -> tuple[QtWidgets.QWidget, dict]:
    """
    Фабричная функция, которая создает единую, объединенную панель настроек мира.
    """
    scroll_area = QtWidgets.QScrollArea()
    scroll_area.setWidgetResizable(True)
    scroll_area.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)

    root = QtWidgets.QWidget()
    scroll_area.setWidget(root)

    layout = QtWidgets.QVBoxLayout(root)
    layout.setContentsMargins(8, 8, 8, 8)
    layout.setSpacing(6)

    widgets = {}

    # --- Секция: Топология и Масштаб ---
    world_box = CollapsibleBox("Топология и Масштаб")
    world_box.setChecked(True)

    widgets["subdivision_level_input"] = QtWidgets.QComboBox()
    widgets["subdivision_level_input"].addItems(SUBDIVISION_LEVELS.keys())
    widgets["subdivision_level_input"].setCurrentText("8 (642 регионов)")
    world_box.body.addRow("Частота разделения:", widgets["subdivision_level_input"])

    widgets["planet_preview_detail_input"] = QtWidgets.QComboBox()
    widgets["planet_preview_detail_input"].addItems(["Низкая (2)", "Средняя (3)", "Высокая (4)"])
    widgets["planet_preview_detail_input"].setCurrentText("Средняя (3)")
    widgets["planet_preview_detail_input"].setToolTip("Уровень детализации 3D-вида планеты.")
    world_box.body.addRow("Детализация планеты:", widgets["planet_preview_detail_input"])

    widgets["region_resolution_input"] = QtWidgets.QComboBox()
    widgets["region_resolution_input"].addItems(ALLOWED_RESOLUTIONS)
    widgets["region_resolution_input"].setCurrentText("1024x1024")
    world_box.body.addRow("Разрешение региона:", widgets["region_resolution_input"])

    widgets["vertex_distance_input"] = QtWidgets.QDoubleSpinBox()
    widgets["vertex_distance_input"].setDecimals(2)
    widgets["vertex_distance_input"].setSingleStep(1.0)
    world_box.body.addRow("Расстояние м/вершина:", widgets["vertex_distance_input"])

    widgets["max_height_input"] = QtWidgets.QDoubleSpinBox()
    widgets["max_height_input"].setReadOnly(True)
    widgets["max_height_input"].setButtonSymbols(QtWidgets.QAbstractSpinBox.ButtonSymbols.NoButtons)
    widgets["max_height_input"].setRange(1.0, 999999.0)
    widgets["max_height_input"].setValue(4000.0)
    widgets["max_height_input"].setDecimals(0)
    widgets["max_height_input"].setToolTip("Вычисляется автоматически.")
    world_box.body.addRow("Макс. Высота (м):", widgets["max_height_input"])

    layout.addWidget(world_box)

    # --- Секция: Вычисляемые параметры (ВОССТАНОВЛЕНА ВАША ВЕРСИЯ) ---
    calc_box = CollapsibleBox("Вычисляемые параметры")
    calc_box.setChecked(True)
    widgets["planet_radius_label"] = QtWidgets.QLabel("0 км")
    calc_box.body.addRow("<i>Радиус планеты:</i>", widgets["planet_radius_label"])

    widgets["surface_area_label"] = QtWidgets.QLabel("0 км²")
    calc_box.body.addRow("<i>Площадь поверхности:</i>", widgets["surface_area_label"])

    widgets["ocean_area_label"] = QtWidgets.QLabel("0 км² (0%)")
    calc_box.body.addRow("<i>Площадь океанов (прибл.):</i>", widgets["ocean_area_label"])

    widgets["base_elevation_label"] = QtWidgets.QLabel("0 м")
    calc_box.body.addRow("<i>Базовый перепад высот:</i>", widgets["base_elevation_label"])

    widgets["land_elevation_label"] = QtWidgets.QLabel("до +0 м")
    calc_box.body.addRow("<i>Высота суши:</i>", widgets["land_elevation_label"])

    widgets["ocean_depth_label"] = QtWidgets.QLabel("до -0 м")
    calc_box.body.addRow("<i>Глубина океана:</i>", widgets["ocean_depth_label"])

    layout.addWidget(calc_box)
    # --- КОНЕЦ ВОССТАНОВЛЕННОГО БЛОКА ---

    # --- Секция: Форма Планеты (Глобальный Шум) ---
    noise_box = CollapsibleBox("Форма Планеты (Глобальный Шум)")
    noise_box.setChecked(True)

    widgets["planet_type_preset_input"] = QtWidgets.QComboBox()
    widgets["planet_type_preset_input"].addItems(PLANET_ROUGHNESS_PRESETS.keys())
    widgets["planet_type_preset_input"].setCurrentText("Землеподобная (0.3%)")
    noise_box.body.addRow("Тип (шероховатость):", widgets["planet_type_preset_input"])

    widgets["ws_continent_scale_km"] = QtWidgets.QDoubleSpinBox()
    widgets["ws_continent_scale_km"].setRange(100.0, 50000.0)
    widgets["ws_continent_scale_km"].setValue(4000.0)
    widgets["ws_continent_scale_km"].setDecimals(0)
    widgets["ws_continent_scale_km"].setSingleStep(100)
    noise_box.body.addRow("Размер континентов (км):", widgets["ws_continent_scale_km"])

    widgets["ws_octaves"] = SliderSpinCombo()
    widgets["ws_octaves"].setRange(1, 16)
    widgets["ws_octaves"].setValue(8)
    widgets["ws_octaves"].setDecimals(0)
    noise_box.body.addRow("Октавы:", widgets["ws_octaves"])

    widgets["ws_gain"] = SliderSpinCombo()
    widgets["ws_gain"].setRange(0.0, 1.0)
    widgets["ws_gain"].setValue(0.5)
    noise_box.body.addRow("Gain (Roughness):", widgets["ws_gain"])

    widgets["ws_power"] = SliderSpinCombo()
    widgets["ws_power"].setRange(0.1, 5.0)
    widgets["ws_power"].setValue(1.0)
    noise_box.body.addRow("Power:", widgets["ws_power"])

    widgets["ws_warp_strength"] = SliderSpinCombo()
    widgets["ws_warp_strength"].setRange(0.0, 1.0)
    widgets["ws_warp_strength"].setValue(0.2)
    noise_box.body.addRow("Warp Strength:", widgets["ws_warp_strength"])

    widgets["ws_seed"] = SeedWidget()
    noise_box.body.addRow("Seed:", widgets["ws_seed"])

    layout.addWidget(noise_box)
    widgets["ws_noise_box"] = noise_box

    # --- Секция: Климат ---
    climate_box = CollapsibleBox("Климат")
    climate_box.setChecked(True)
    widgets["climate_enabled"] = QtWidgets.QCheckBox("Включить глобальный климат")
    climate_box.body.addRow(widgets["climate_enabled"])

    widgets["climate_sea_level"] = SliderSpinCombo()
    widgets["climate_sea_level"].setRange(0.0, 100.0)
    widgets["climate_sea_level"].setValue(40.0)
    widgets["climate_sea_level"].setDecimals(1)
    climate_box.body.addRow("Уровень моря (%):", widgets["climate_sea_level"])

    widgets["climate_avg_temp"] = SliderSpinCombo()
    widgets["climate_avg_temp"].setRange(-20.0, 40.0)
    widgets["climate_avg_temp"].setValue(15.0)
    widgets["climate_avg_temp"].setDecimals(1)
    climate_box.body.addRow("Средняя t (°C):", widgets["climate_avg_temp"])

    widgets["climate_axis_tilt"] = SliderSpinCombo()
    widgets["climate_axis_tilt"].setRange(0.0, 45.0)
    widgets["climate_axis_tilt"].setValue(23.5)
    widgets["climate_axis_tilt"].setDecimals(1)
    climate_box.body.addRow("Наклон оси (°):", widgets["climate_axis_tilt"])

    climate_box.body.addRow(QtWidgets.QLabel("<b>Влажность и Ветер:</b>"))

    widgets["climate_wind_dir"] = SliderSpinCombo()
    widgets["climate_wind_dir"].setRange(0.0, 360.0)
    widgets["climate_wind_dir"].setValue(225.0)
    widgets["climate_wind_dir"].setDecimals(0)
    climate_box.body.addRow("Направление ветра (°):", widgets["climate_wind_dir"])

    widgets["climate_shadow_strength"] = SliderSpinCombo()
    widgets["climate_shadow_strength"].setRange(0.0, 1.0)
    widgets["climate_shadow_strength"].setValue(0.6)
    widgets["climate_shadow_strength"].setDecimals(2)
    climate_box.body.addRow("Сила дождевой тени:", widgets["climate_shadow_strength"])

    layout.addWidget(climate_box)

    # --- Секция: Настройки Превью ---
    preview_box = CollapsibleBox("Настройки Превью")
    preview_box.setChecked(True)

    # --- НОВЫЙ ЭЛЕМЕНТ ИНТЕГРИРОВАН СЮДА ---
    widgets["preview_calc_resolution_input"] = QtWidgets.QComboBox()
    widgets["preview_calc_resolution_input"].addItems(
        ["Полное разрешение", "2048x2048", "1024x1024", "512x512", "256x256"])
    widgets["preview_calc_resolution_input"].setCurrentText("1024x1024")
    widgets["preview_calc_resolution_input"].setToolTip("Разрешение, в котором рассчитывается граф (меньше = быстрее)")
    preview_box.body.addRow("Разрешение вычислений:", widgets["preview_calc_resolution_input"])

    widgets["preview_resolution_input"] = QtWidgets.QComboBox()
    widgets["preview_resolution_input"].addItems(["512x512", "1024x1024", "2048x2048"])
    widgets["preview_resolution_input"].setCurrentText("1024x1024")
    preview_box.body.addRow("Разрешение 3D-вида:", widgets["preview_resolution_input"])

    widgets["region_id_label"] = QtWidgets.QLabel("0")
    preview_box.body.addRow("ID Региона:", widgets["region_id_label"])
    widgets["region_center_x_label"] = QtWidgets.QLabel("0.0")
    preview_box.body.addRow("Центр X (сфер. коорд.):", widgets["region_center_x_label"])
    widgets["region_center_z_label"] = QtWidgets.QLabel("0.0")
    preview_box.body.addRow("Центр Z (сфер. коорд.):", widgets["region_center_z_label"])
    widgets["biome_probabilities_list"] = QtWidgets.QListWidget()
    widgets["biome_probabilities_list"].setMinimumHeight(80)
    preview_box.body.addRow("Вероятные биомы:", widgets["biome_probabilities_list"])
    layout.addWidget(preview_box)
    layout.addStretch()

    # Пустышка для обратной совместимости
    widgets["ws_sea_level"] = QtWidgets.QWidget()
    widgets["ws_sea_level"].value = lambda: 0.0
    widgets["ws_relative_scale"] = QtWidgets.QWidget()
    widgets["ws_relative_scale"].value = lambda: 0.25

    return scroll_area, widgets