# editor/ui_panels/render_panel.py
from __future__ import annotations
from typing import Callable
from PySide6 import QtWidgets, QtCore

# Обновленные импорты
from editor.core.render_settings import RenderSettings, RENDER_PRESETS
from editor.render_palettes import PALETTES


def _create_spin_row(label: str, value: float, min_val: float, max_val: float, step: float, decimals: int = 1):
    box = QtWidgets.QDoubleSpinBox()
    box.setRange(min_val, max_val)
    box.setSingleStep(step)
    box.setDecimals(decimals)
    box.setValue(value)
    row = QtWidgets.QHBoxLayout()
    row.addWidget(QtWidgets.QLabel(label))
    row.addWidget(box)
    return box, row


class RenderPanel(QtWidgets.QWidget):
    changed = QtCore.Signal(object)

    def __init__(self, settings: RenderSettings, parent=None):
        super().__init__(parent)
        self.s = settings
        self._block_signals = False

        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(6)

        # --- Пресеты ---
        top_layout = QtWidgets.QHBoxLayout()
        top_layout.addWidget(QtWidgets.QLabel("Пресет:"))
        self.preset_box = QtWidgets.QComboBox()
        self.preset_box.addItems(["Custom"] + list(RENDER_PRESETS.keys()))
        top_layout.addWidget(self.preset_box, 1)
        self.apply_btn = QtWidgets.QPushButton("Применить")
        top_layout.addWidget(self.apply_btn)
        lay.addLayout(top_layout)

        lay.addWidget(
            QtWidgets.QFrame(self, frameShape=QtWidgets.QFrame.Shape.HLine, frameShadow=QtWidgets.QFrame.Shadow.Sunken))

        # --- Режим света ---
        mode_row = QtWidgets.QHBoxLayout()
        mode_row.addWidget(QtWidgets.QLabel("Режим света:"))
        self.mode = QtWidgets.QComboBox()
        self.mode.addItems(["world", "headlight"])
        self.mode.setCurrentText(self.s.light_mode)
        mode_row.addWidget(self.mode, 1)
        lay.addLayout(mode_row)

        # --- Поля настроек ---
        self.az, row = _create_spin_row("Азимут (°)", self.s.light_azimuth_deg, 0, 360, 5, 0)
        lay.addLayout(row)
        self.al, row = _create_spin_row("Высота (°)", self.s.light_altitude_deg, 0, 90, 2, 0)
        lay.addLayout(row)
        self.amb, row = _create_spin_row("Ambient", self.s.ambient, 0, 1, 0.02, 2)
        lay.addLayout(row)
        self.dif, row = _create_spin_row("Diffuse", self.s.diffuse, 0, 2, 0.05, 2)
        lay.addLayout(row)
        self.spe, row = _create_spin_row("Specular", self.s.specular, 0, 0.3, 0.01, 2)
        lay.addLayout(row)
        self.shi, row = _create_spin_row("Shininess", self.s.shininess, 4, 128, 2, 0)
        lay.addLayout(row)
        lay.addSpacing(6)
        self.hex, row = _create_spin_row("Высота ×", self.s.height_exaggeration, 0.5, 3.0, 0.05, 2)
        lay.addLayout(row)
        self.hex.setObjectName("height_exaggeration_spinbox")
        self.fov, row = _create_spin_row("FOV (°)", self.s.fov, 30, 80, 1, 0)
        lay.addLayout(row)

        self.auto = QtWidgets.QCheckBox("Auto frame")
        self.auto.setChecked(self.s.auto_frame)
        lay.addWidget(self.auto)

        # --- НОВОЕ: блок цвета ---
        grp = QtWidgets.QGroupBox("Цвет (предпросмотр)")
        v = QtWidgets.QVBoxLayout(grp)

        self.use_palette = QtWidgets.QCheckBox("Использовать палитру по высоте")
        self.use_palette.setChecked(self.s.use_palette)
        v.addWidget(self.use_palette)

        h = QtWidgets.QHBoxLayout()
        h.addWidget(QtWidgets.QLabel("Палитра:"))
        self.palette = QtWidgets.QComboBox()
        self.palette.addItems(list(PALETTES.keys()))
        self.palette.setCurrentText(self.s.palette_name)
        h.addWidget(self.palette, 1)
        v.addLayout(h)

        self.use_slope = QtWidgets.QCheckBox("Slope Darkening (затемнять крутые склоны)")
        self.use_slope.setChecked(self.s.use_slope_darkening)
        v.addWidget(self.use_slope)

        h2 = QtWidgets.QHBoxLayout()
        h2.addWidget(QtWidgets.QLabel("Сила:"))
        self.slope_strength = QtWidgets.QDoubleSpinBox()
        self.slope_strength.setRange(0.0, 1.0)
        self.slope_strength.setDecimals(2)
        self.slope_strength.setSingleStep(0.05)
        self.slope_strength.setValue(self.s.slope_strength)
        h2.addWidget(self.slope_strength, 1)
        v.addLayout(h2)

        lay.addWidget(grp)

        # --- Кнопки ---
        btns = QtWidgets.QHBoxLayout()
        self.reset_btn = QtWidgets.QPushButton("Сброс")
        btns.addStretch(1)
        btns.addWidget(self.reset_btn)
        lay.addLayout(btns)
        lay.addStretch(1)

        # --- Сигналы ---
        all_spinboxes = (self.az, self.al, self.amb, self.dif, self.spe, self.shi, self.hex, self.fov)
        for w in all_spinboxes:
            w.valueChanged.connect(self._emit_changes)
        self.auto.toggled.connect(self._emit_changes)
        self.reset_btn.clicked.connect(self._reset)
        self.apply_btn.clicked.connect(self._apply_preset)
        self.mode.currentTextChanged.connect(self._emit_changes)

        # Новые сигналы
        self.use_palette.toggled.connect(self._emit_changes)
        self.palette.currentTextChanged.connect(self._emit_changes)
        self.use_slope.toggled.connect(self._emit_changes)
        self.slope_strength.valueChanged.connect(self._emit_changes)

    def _apply_preset(self):
        name = self.preset_box.currentText()
        if name == "Custom": return

        data = RENDER_PRESETS.get(name, {})
        new_settings = RenderSettings.from_dict(data)
        self.set_settings(new_settings)
        self._emit_changes()

    def _emit_changes(self):
        if self._block_signals:
            return

        self.s.light_azimuth_deg = float(self.az.value())
        self.s.light_altitude_deg = float(self.al.value())
        self.s.ambient = float(self.amb.value())
        self.s.diffuse = float(self.dif.value())
        self.s.specular = float(self.spe.value())
        self.s.shininess = float(self.shi.value())
        self.s.height_exaggeration = float(self.hex.value())
        self.s.fov = float(self.fov.value())
        self.s.auto_frame = bool(self.auto.isChecked())
        self.s.light_mode = self.mode.currentText()

        # Новые поля
        self.s.use_palette = bool(self.use_palette.isChecked())
        self.s.palette_name = self.palette.currentText()
        self.s.use_slope_darkening = bool(self.use_slope.isChecked())
        self.s.slope_strength = float(self.slope_strength.value())

        if self.preset_box.currentText() != "Custom":
            self.preset_box.setCurrentText("Custom")

        self.changed.emit(self.s)

    def set_settings(self, settings: RenderSettings):
        self._block_signals = True
        try:
            self.s = settings
            self.az.setValue(self.s.light_azimuth_deg)
            self.al.setValue(self.s.light_altitude_deg)
            self.amb.setValue(self.s.ambient)
            self.dif.setValue(self.s.diffuse)
            self.spe.setValue(self.s.specular)
            self.shi.setValue(self.s.shininess)
            self.hex.setValue(self.s.height_exaggeration)
            self.fov.setValue(self.s.fov)
            self.auto.setChecked(self.s.auto_frame)
            self.mode.setCurrentText(self.s.light_mode)

            # Новые поля
            self.use_palette.setChecked(settings.use_palette)
            self.palette.setCurrentText(settings.palette_name)
            self.use_slope.setChecked(settings.use_slope_darkening)
            self.slope_strength.setValue(settings.slope_strength)
        finally:
            self._block_signals = False

    def _reset(self):
        self.set_settings(RenderSettings())
        self._emit_changes()


# Фабрика для V2 архитектуры
def make_render_panel_widget(main_window, settings: RenderSettings, on_changed: Callable) -> RenderPanel:
    panel = RenderPanel(settings, main_window)
    panel.changed.connect(on_changed)
    return panel


# Фабрика для V1/Legacy архитектуры
def create_render_dock(main_window, settings: RenderSettings, on_changed: Callable) -> QtWidgets.QDockWidget:
    dock = QtWidgets.QDockWidget("Рендер", main_window)
    panel = RenderPanel(settings, dock)
    panel.changed.connect(on_changed)

    dock.setWidget(panel)
    dock.setObjectName("RenderDock")
    dock.setAllowedAreas(QtCore.Qt.DockWidgetArea.LeftDockWidgetArea | QtCore.Qt.DockWidgetArea.RightDockWidgetArea)
    main_window.addDockWidget(QtCore.Qt.DockWidgetArea.RightDockWidgetArea, dock)
    return dock
