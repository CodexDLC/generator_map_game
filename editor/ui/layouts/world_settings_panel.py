# editor/ui/layouts/world_settings_panel.py
from __future__ import annotations
from PySide6 import QtWidgets, QtCore

from editor.ui.widgets.custom_controls import CollapsibleBox, SliderSpinCombo, SeedWidget

SUBDIVISION_LEVELS = {
    "3 (92 регионов)": 92, "5 (252 регионов)": 252, "8 (642 регионов)": 642,
    "10 (1002 регионов)": 1002, "16 (2562 регионов)": 2562, "32 (10242 регионов)": 10242,
}
ALLOWED_RESOLUTIONS = ["1024x1024", "2048x2048", "4096x4096"]
MAX_SIDE_METERS = 65536.0

# --- НОВЫЙ СЛОВАРЬ ПРЕСЕТОВ ШЕРОХОВАТОСТИ ---
PLANET_ROUGHNESS_PRESETS = {
    # Имя в UI: (Процент от радиуса, Коэффициент запаса для макс. высоты)
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

    # --- БЛОК 1: ГЛОБАЛЬНЫЕ НАСТРОЙКИ ---
    world_box = CollapsibleBox("Глобальные Настройки")
    world_box.setChecked(True)

    # --- Группа 1: Топология и Масштаб ---
    world_box.body.addRow(QtWidgets.QLabel("<b>Топология и Масштаб</b>"))

    widgets["subdivision_level_input"] = QtWidgets.QComboBox()
    widgets["subdivision_level_input"].addItems(SUBDIVISION_LEVELS.keys())
    widgets["subdivision_level_input"].setCurrentText("8 (642 регионов)")
    world_box.body.addRow("Частота разделения:", widgets["subdivision_level_input"])

    widgets["planet_preview_detail_input"] = QtWidgets.QComboBox()
    widgets["planet_preview_detail_input"].addItems([
        "Низкая (2)", "Средняя (3)", "Высокая (4)"
    ])
    widgets["planet_preview_detail_input"].setCurrentText("Средняя (3)")
    widgets["planet_preview_detail_input"].setToolTip(
        "Уровень детализации 3D-вида планеты.\n"
        "Высокие значения могут замедлить обновление."
    )
    world_box.body.addRow("Детализация планеты:", widgets["planet_preview_detail_input"])

    widgets["region_resolution_input"] = QtWidgets.QComboBox()
    widgets["region_resolution_input"].addItems(ALLOWED_RESOLUTIONS)
    widgets["region_resolution_input"].setCurrentText("4096x4096")
    world_box.body.addRow("Разрешение региона:", widgets["region_resolution_input"])

    widgets["vertex_distance_input"] = QtWidgets.QDoubleSpinBox()
    widgets["vertex_distance_input"].setDecimals(2)
    widgets["vertex_distance_input"].setSingleStep(0.25)
    world_box.body.addRow("Расстояние м/вершина:", widgets["vertex_distance_input"])

    # --- ИЗМЕНЕНИЕ: Поле Макс. Высота теперь только для чтения ---
    widgets["max_height_input"] = QtWidgets.QDoubleSpinBox()
    widgets["max_height_input"].setReadOnly(True)
    widgets["max_height_input"].setButtonSymbols(QtWidgets.QAbstractSpinBox.ButtonSymbols.NoButtons)
    widgets["max_height_input"].setRange(1.0, 999999.0)
    widgets["max_height_input"].setValue(4000.0)
    widgets["max_height_input"].setDecimals(0)
    widgets["max_height_input"].setToolTip("Вычисляется автоматически на основе типа планеты и радиуса.")
    world_box.body.addRow("Макс. Высота (м):", widgets["max_height_input"])

    # --- Группа 2: Форма Планеты (Глобальный Шум) ---
    world_box.body.addRow(QtWidgets.QLabel("---"))
    world_box.body.addRow(QtWidgets.QLabel("<b>Форма Планеты (Глобальный Шум)</b>"))

    # --- ИЗМЕНЕНИЕ: Замена слайдера на выпадающий список пресетов ---
    widgets["planet_type_preset_input"] = QtWidgets.QComboBox()
    widgets["planet_type_preset_input"].addItems(PLANET_ROUGHNESS_PRESETS.keys())
    widgets["planet_type_preset_input"].setCurrentText("Землеподобная (0.3%)")
    world_box.body.addRow("Тип планеты (шероховатость):", widgets["planet_type_preset_input"])

    widgets["ws_sea_level"] = SliderSpinCombo()
    widgets["ws_sea_level"].setRange(0.0, 1.0)
    widgets["ws_sea_level"].setValue(0.4)
    world_box.body.addRow("Уровень моря (% от перепада):", widgets["ws_sea_level"])

    widgets["ws_relative_scale"] = SliderSpinCombo()
    widgets["ws_relative_scale"].setRange(0.01, 1.0)
    widgets["ws_relative_scale"].setValue(0.25)
    world_box.body.addRow("Масштаб континентов:", widgets["ws_relative_scale"])

    widgets["ws_octaves"] = SliderSpinCombo()
    widgets["ws_octaves"].setRange(1, 16)
    widgets["ws_octaves"].setValue(8)
    widgets["ws_octaves"].setDecimals(0)
    world_box.body.addRow("Октавы:", widgets["ws_octaves"])

    widgets["ws_gain"] = SliderSpinCombo()
    widgets["ws_gain"].setRange(0.0, 1.0)
    widgets["ws_gain"].setValue(0.5)
    world_box.body.addRow("Gain (Roughness):", widgets["ws_gain"])

    widgets["ws_power"] = SliderSpinCombo()
    widgets["ws_power"].setRange(0.1, 5.0)
    widgets["ws_power"].setValue(1.0)
    world_box.body.addRow("Power:", widgets["ws_power"])

    widgets["ws_warp_strength"] = SliderSpinCombo()
    widgets["ws_warp_strength"].setRange(0.0, 1.0)
    widgets["ws_warp_strength"].setValue(0.2)
    world_box.body.addRow("Warp Strength:", widgets["ws_warp_strength"])

    widgets["ws_seed"] = SeedWidget()
    world_box.body.addRow("Seed:", widgets["ws_seed"])

    # --- Группа 3: Вычисляемые Параметры ---
    world_box.body.addRow(QtWidgets.QLabel("---"))
    world_box.body.addRow(QtWidgets.QLabel("<b>Вычисляемые параметры</b>"))

    widgets["planet_radius_label"] = QtWidgets.QLabel("0 км")
    widgets["planet_radius_label"].setAlignment(QtCore.Qt.AlignRight)
    world_box.body.addRow("<i>Радиус планеты:</i>", widgets["planet_radius_label"])

    widgets["base_elevation_label"] = QtWidgets.QLabel("0 м")
    widgets["base_elevation_label"].setAlignment(QtCore.Qt.AlignRight)
    world_box.body.addRow("<i>Базовый перепад высот:</i>", widgets["base_elevation_label"])

    layout.addWidget(world_box)

    # --- БЛОК 2: НАСТРОЙКИ ПРЕВЬЮ ---
    preview_box = CollapsibleBox("Настройки Превью")
    preview_box.setChecked(True)

    widgets["preview_resolution_input"] = QtWidgets.QComboBox()
    widgets["preview_resolution_input"].addItems(["1024x1024", "2048x2048", "4096x4096"])
    widgets["preview_resolution_input"].setCurrentText("1024x1024")
    preview_box.body.addRow("Разрешение превью:", widgets["preview_resolution_input"])

    widgets["region_id_label"] = QtWidgets.QLabel("0")
    preview_box.body.addRow("ID Региона:", widgets["region_id_label"])

    widgets["region_center_x_label"] = QtWidgets.QLabel("0.0")
    preview_box.body.addRow("Центр X (сфер. коорд.):", widgets["region_center_x_label"])

    widgets["region_center_z_label"] = QtWidgets.QLabel("0.0")
    preview_box.body.addRow("Центр Z (сфер. коорд.):", widgets["region_center_z_label"])

    layout.addWidget(preview_box)
    layout.addStretch()

    widgets["ws_noise_box"] = world_box

    return scroll_area, widgets