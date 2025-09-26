# Вверху файла:
from NodeGraphQt.widgets.node_widgets import NodeBaseWidget
from PySide6.QtGui import QTextOption
from PySide6 import QtWidgets, QtCore

class ReadOnlyTextWidget(NodeBaseWidget):
    """
    Обёртка NodeGraphQt вокруг QTextEdit (read-only), чтобы её можно было
    класть через add_custom_widget.
    """
    def __init__(self, name='about_desc', label='Description', text=''):
        super().__init__(name=name, label=label)


        te = QtWidgets.QTextEdit()
        te.setReadOnly(True)
        te.setMinimumHeight(140)
        te.setLineWrapMode(QtWidgets.QTextEdit.LineWrapMode.WidgetWidth)
        te.setWordWrapMode(QTextOption.WrapMode.WordWrap)
        te.setPlainText(text)

        # Сообщаем NodeGraphQt, какой QWidget мы показываем
        self.set_custom_widget(te)

    # API NodeBaseWidget — чтобы NodeGraphQt умел читать/писать значение
    def get_value(self):
        return self._custom_widget.toPlainText()

    def set_value(self, value):
        self._custom_widget.setPlainText(str(value))
