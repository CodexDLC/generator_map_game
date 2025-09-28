# editor/widgets/slider_widget.py
from PySide6 import QtWidgets, QtCore
from NodeGraphQt import NodeBaseWidget


class SliderWidget(NodeBaseWidget):
    """
    Кастомный виджет, объединяющий ползунок (QSlider) и
    поле для ввода числа (QDoubleSpinBox).
    """

    def __init__(self, name='', label='', min_val=0.0, max_val=1.0, decimals=2, parent=None):
        super(SliderWidget, self).__init__(parent=parent, name=name, label=label)

        self.wrapper = QtWidgets.QWidget()
        self.layout = QtWidgets.QHBoxLayout(self.wrapper)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(4)

        # Создаем SpinBox для точного ввода
        self.spinbox = QtWidgets.QDoubleSpinBox()
        self.spinbox.setRange(min_val, max_val)
        self.spinbox.setDecimals(decimals)
        self.spinbox.setButtonSymbols(QtWidgets.QAbstractSpinBox.ButtonSymbols.NoButtons)

        # Создаем Slider
        self.slider = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
        self._slider_mult = 10 ** decimals
        self.slider.setRange(int(min_val * self._slider_mult), int(max_val * self._slider_mult))

        self.layout.addWidget(self.spinbox)
        self.layout.addWidget(self.slider)
        self.set_custom_widget(self.wrapper)

        # Соединяем сигналы
        self.slider.valueChanged.connect(self._on_slider_change)
        self.spinbox.valueChanged.connect(self._on_spinbox_change)

    def _on_slider_change(self, value):
        # Блокируем сигналы, чтобы не было бесконечного цикла
        self.spinbox.blockSignals(True)
        self.spinbox.setValue(float(value) / self._slider_mult)
        self.spinbox.blockSignals(False)
        self.on_value_changed(self.name, self.get_value())

    def _on_spinbox_change(self, value):
        self.slider.blockSignals(True)
        self.slider.setValue(int(value * self._slider_mult))
        self.slider.blockSignals(False)
        self.on_value_changed(self.name, self.get_value())

    def get_value(self):
        return self.spinbox.value()

    def set_value(self, value):
        self._on_spinbox_change(float(value))