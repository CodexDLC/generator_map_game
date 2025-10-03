# editor/ui/layouts/world_settings_panel.py
from __future__ import annotations
from PySide6 import QtWidgets, QtCore

from editor.ui.widgets.custom_controls import CollapsibleBox, SliderSpinCombo, SeedWidget

# Константы (остаются без изменений)
SUBDIVISION_LEVELS = {
    "3 (92 регионов)": 92, "5 (252 регионов)": 252, "8 (642 регионов)": 642,
    "10 (1002 регионов)": 1002, "16 (2562 регионов)": 2562, "32 (10242 регионов)": 10242,
}
ALLOWED_RESOLUTIONS = ["2048x2048", "4096x4096", "8192x8192", "16384x16384"]
MAX_SIDE_METERS = 65536.0


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

    # --- ЕДИНЫЙ БЛОК ДЛЯ ВСЕХ НАСТРОЕК ---
    world_box = CollapsibleBox("Глобальные Настройки")
    world_box.setChecked(True)  # По умолчанию раскрыт

    # --- Группа 1: Топология и Масштаб ---
    world_box.body.addRow(QtWidgets.QLabel("<b>Топология и Масштаб</b>"))

    widgets["subdivision_level_input"] = QtWidgets.QComboBox()
    widgets["subdivision_level_input"].addItems(SUBDIVISION_LEVELS.keys())
    widgets["subdivision_level_input"].setCurrentText("8 (642 регионов)")
    world_box.body.addRow("Частота разделения:", widgets["subdivision_level_input"])

    widgets["region_resolution_input"] = QtWidgets.QComboBox()
    widgets["region_resolution_input"].addItems(ALLOWED_RESOLUTIONS)
    widgets["region_resolution_input"].setCurrentText("4096x4096")
    world_box.body.addRow("Разрешение региона:", widgets["region_resolution_input"])

    widgets["vertex_distance_input"] = QtWidgets.QDoubleSpinBox()
    widgets["vertex_distance_input"].setDecimals(2)
    widgets["vertex_distance_input"].setSingleStep(0.25)
    world_box.body.addRow("Расстояние м/вершина:", widgets["vertex_distance_input"])

    widgets["max_height_input"] = QtWidgets.QDoubleSpinBox()
    widgets["max_height_input"].setRange(1.0, 50000.0)
    widgets["max_height_input"].setValue(8000.0)
    widgets["max_height_input"].setDecimals(0)
    world_box.body.addRow("Макс. Высота (м):", widgets["max_height_input"])

    # --- Группа 2: Форма Планеты (Глобальный Шум) ---
    world_box.body.addRow(QtWidgets.QLabel("---"))
    world_box.body.addRow(QtWidgets.QLabel("<b>Форма Планеты (Глобальный Шум)</b>"))

    widgets["ws_sea_level"] = SliderSpinCombo()
    widgets["ws_sea_level"].setRange(0.0, 1.0)
    widgets["ws_sea_level"].setValue(0.4)
    world_box.body.addRow("Уровень моря (карта):", widgets["ws_sea_level"])

    widgets["ws_relative_scale"] = SliderSpinCombo()
    widgets["ws_relative_scale"].setRange(0.01, 1.0)
    widgets["ws_relative_scale"].setValue(0.25)
    world_box.body.addRow("Масштаб континентов:", widgets["ws_relative_scale"])

    widgets["ws_sphere_octaves"] = SliderSpinCombo()
    widgets["ws_sphere_octaves"].setRange(1, 16)
    widgets["ws_sphere_octaves"].setValue(8)
    widgets["ws_sphere_octaves"].setDecimals(0)
    world_box.body.addRow("Октавы:", widgets["ws_sphere_octaves"])

    widgets["ws_sphere_gain"] = SliderSpinCombo()
    widgets["ws_sphere_gain"].setRange(0.0, 1.0)
    widgets["ws_sphere_gain"].setValue(0.5)
    world_box.body.addRow("Gain (Roughness):", widgets["ws_sphere_gain"])

    widgets["ws_sphere_ridge"] = QtWidgets.QCheckBox("Гребни (Ridged)")
    world_box.body.addRow("", widgets["ws_sphere_ridge"])

    widgets["ws_sphere_seed"] = SeedWidget()
    world_box.body.addRow("Seed:", widgets["ws_sphere_seed"])

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
    layout.addStretch()

    # Сохраняем ссылку на сам CollapsibleBox для main_window
    widgets["ws_noise_box"] = world_box

    return scroll_area, widgets