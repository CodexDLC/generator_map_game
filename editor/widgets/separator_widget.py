# editor/widgets/separator_widget.py
from PySide6 import QtWidgets
from NodeGraphQt import NodeBaseWidget

class SeparatorWidget(NodeBaseWidget):
    """Виджет, который отображает линию с текстом для группировки свойств."""

    def __init__(self, name='_sep', label=''):
        super().__init__(name=name, label='')
        wrapper = QtWidgets.QWidget()
        layout = QtWidgets.QHBoxLayout(wrapper)
        layout.setContentsMargins(0, 12, 0, 4)  # Отступы сверху и снизу

        line = QtWidgets.QFrame()
        line.setFrameShape(QtWidgets.QFrame.Shape.HLine)
        line.setFrameShadow(QtWidgets.QFrame.Shadow.Sunken)
        layout.addWidget(line)

        if label:
            text = QtWidgets.QLabel(f' {label.upper()} ')
            text.setStyleSheet("background-color: #323232; color: #aaa; border: 1px solid #2b2b2b; border-radius: 3px;")
            layout.addWidget(text)
            layout.addStretch()

        self.set_custom_widget(wrapper)

    def get_value(self): return None
    def set_value(self, value): pass