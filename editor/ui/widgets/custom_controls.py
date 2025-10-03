# editor/ui/widgets/custom_controls.py
from __future__ import annotations
import random
from typing import List, Optional

from PySide6 import QtWidgets, QtCore, QtGui
from PySide6.QtCore import Qt


class SeedWidget(QtWidgets.QWidget):
    valueChanged = QtCore.Signal(float)
    editingFinished = QtCore.Signal()

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        self._block_signals = False
        self.spinbox = QtWidgets.QDoubleSpinBox()
        self.spinbox.setRange(0, 4294967295)
        self.spinbox.setDecimals(0)
        self.spinbox.setButtonSymbols(QtWidgets.QAbstractSpinBox.ButtonSymbols.NoButtons)
        self.generate_btn = QtWidgets.QToolButton()
        self.generate_btn.setText("🎲")
        self.generate_btn.setToolTip("Сгенерировать новый случайный сид")
        self.history_btn = QtWidgets.QToolButton()
        self.history_btn.setText("📖")
        self.history_btn.setToolTip("Показать историю сидов")
        self.history_btn.setPopupMode(QtWidgets.QToolButton.ToolButtonPopupMode.InstantPopup)
        self.history_menu = QtWidgets.QMenu(self)
        self.history_btn.setMenu(self.history_menu)
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        layout.addWidget(self.spinbox, 1)
        layout.addWidget(self.generate_btn)
        layout.addWidget(self.history_btn)
        self.generate_btn.clicked.connect(self.generate_new_seed)
        self.spinbox.valueChanged.connect(self.valueChanged.emit)
        self.spinbox.editingFinished.connect(self.editingFinished.emit)

    def generate_new_seed(self):
        new_seed = random.randint(0, 4294967295)
        self.spinbox.setValue(new_seed)
        self.editingFinished.emit()

    def value(self) -> int:
        return int(self.spinbox.value())

    def setValue(self, value: int):
        self.spinbox.setValue(value)

    def set_history(self, history: List[int]):
        self.history_menu.clear()
        for seed in history:
            action = QtGui.QAction(str(seed), self)
            action.triggered.connect(lambda _, s=seed: self.setValue(s))
            self.history_menu.addAction(action)


class SliderSpinCombo(QtWidgets.QWidget):
    editingFinished = QtCore.Signal()

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None, slider_on_left: bool = True):
        super().__init__(parent)
        self._block_signals = False
        self.slider = QtWidgets.QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(0, 1000)
        self.spinbox = QtWidgets.QDoubleSpinBox()
        self.spinbox.setDecimals(3)
        self.spinbox.setSingleStep(0.01)
        self.spinbox.setButtonSymbols(QtWidgets.QAbstractSpinBox.ButtonSymbols.NoButtons)
        self.spinbox.setFixedWidth(60)
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        if slider_on_left:
            layout.addWidget(self.slider)
            layout.addWidget(self.spinbox)
        else:
            layout.addWidget(self.spinbox)
            layout.addWidget(self.slider)

        self.slider.valueChanged.connect(self._on_slider_change)
        self.spinbox.valueChanged.connect(self._on_spinbox_change)
        self.slider.sliderReleased.connect(self.editingFinished.emit)
        self.spinbox.editingFinished.connect(self.editingFinished.emit)

    def setRange(self, min_val: float, max_val: float):
        self.spinbox.setRange(min_val, max_val)
        self.slider.valueChanged.disconnect()
        self.spinbox.valueChanged.disconnect()
        self.slider.valueChanged.connect(self._on_slider_change)
        self.spinbox.valueChanged.connect(self._on_spinbox_change)

    def setDecimals(self, decimals: int):
        self.spinbox.setDecimals(decimals)

    def value(self) -> float:
        return self.spinbox.value()

    def setValue(self, value: float):
        min_val, max_val = self.spinbox.minimum(), self.spinbox.maximum()
        value = max(min_val, min(max_val, float(value)))
        self._block_signals = True
        try:
            self.spinbox.setValue(value)
            if (max_val - min_val) > 1e-6:
                ratio = (value - min_val) / (max_val - min_val)
                self.slider.setValue(int(ratio * 1000))
        finally:
            self._block_signals = False

    @QtCore.Slot(int)
    def _on_slider_change(self, slider_value: int):
        if self._block_signals: return
        min_val, max_val = self.spinbox.minimum(), self.spinbox.maximum()
        ratio = slider_value / 1000.0
        float_value = min_val + (max_val - min_val) * ratio
        self._block_signals = True
        self.spinbox.setValue(float_value)
        self._block_signals = False

    @QtCore.Slot(float)
    def _on_spinbox_change(self, spinbox_value: float):
        if self._block_signals: return
        min_val, max_val = self.spinbox.minimum(), self.spinbox.maximum()
        if (max_val - min_val) > 1e-6:
            ratio = (spinbox_value - min_val) / (max_val - min_val)
            self._block_signals = True
            self.slider.setValue(int(ratio * 1000))
            self._block_signals = False


class CollapsibleBox(QtWidgets.QGroupBox):
    def __init__(self, title: str, parent=None):
        super().__init__(title, parent)
        self.setObjectName("CollapsibleBox")
        self.setCheckable(True)
        self.setChecked(True)
        self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Preferred, QtWidgets.QSizePolicy.Policy.Minimum)
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(8, 6, 8, 8)
        lay.setSpacing(6)
        self._content = QtWidgets.QWidget(self)
        lay.addWidget(self._content)
        self.body = QtWidgets.QFormLayout(self._content)
        self.body.setContentsMargins(4, 4, 4, 4)
        self.body.setSpacing(6)
        self.toggled.connect(self._content.setVisible)
