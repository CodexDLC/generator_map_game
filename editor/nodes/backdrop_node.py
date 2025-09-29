from NodeGraphQt import BackdropNode  # если нет — from NodeGraphQt import BaseNode
from PySide6.QtGui import QColor

class CustomBackdropNode(BackdropNode):
    __identifier__ = "custom.ui"
    NODE_NAME = "Backdrop"

    def __init__(self):
        super().__init__()
        # доп. свойства для нашей панели
        try:
            self.model.add_property("title", "Backdrop", tab="Node")
            self.model.add_property("color", "#404040", tab="Node")  # hex строка
        except Exception:
            pass

    # вспомогательные методы для цвета
    def set_back_color(self, color_str: str):
        try:
            # нативное API, если есть
            if hasattr(self, "set_color"):
                r, g, b = QColor(color_str).red(), QColor(color_str).green(), QColor(color_str).blue()
                self.set_color(r, g, b)
                return
            gi = self.graphics_item()
            br = gi.brush()
            br.setColor(QColor(color_str))
            gi.setBrush(br)
        except Exception:
            pass

    def set_title(self, text: str):
        try:
            if hasattr(self, "set_name"):
                self.set_name(text)
            else:
                self.set_property("name", text)
        except Exception:
            pass
