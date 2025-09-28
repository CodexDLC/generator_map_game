# editor/widgets/read_only_text_widget.py
from PySide6 import QtWidgets
from PySide6.QtGui import QTextOption
from NodeGraphQt import NodeBaseWidget

class ReadOnlyTextWidget(NodeBaseWidget):
    def __init__(self, name='about_desc', label='Description', text=''):
        super().__init__(name=name, label=label)
        te = QtWidgets.QTextEdit()
        te.setReadOnly(True)
        te.setMinimumHeight(140)
        te.setLineWrapMode(QtWidgets.QTextEdit.LineWrapMode.WidgetWidth)
        te.setWordWrapMode(QTextOption.WrapMode.WordWrap)
        te.setPlainText(text)
        self.set_custom_widget(te)

    def get_value(self):
        return self._custom_widget.toPlainText()

    def set_value(self, value):
        self._custom_widget.setPlainText(str(value))