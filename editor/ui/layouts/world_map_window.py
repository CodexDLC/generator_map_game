# editor/ui/world_map_window.py
from __future__ import annotations
import logging
from typing import TYPE_CHECKING

from PySide6 import QtWidgets, QtCore, QtGui

if TYPE_CHECKING:
    from editor.core.main_window import MainWindow

logger = logging.getLogger(__name__)


class InteractiveMapLabel(QtWidgets.QLabel):
    """
    Лейбл, который отлавливает клики мыши и сообщает относительные координаты.
    """
    map_clicked = QtCore.Signal(float, float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(512, 256)
        self.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.setText("Нажмите 'Обновить', чтобы сгенерировать карту мира")

    def mousePressEvent(self, ev: QtGui.QMouseEvent):
        pixmap = self.pixmap()
        if not pixmap or pixmap.isNull():
            super().mousePressEvent(ev)
            return

        pixmap_rect = pixmap.rect()
        label_rect = self.rect()

        x_offset = (label_rect.width() - pixmap_rect.width()) / 2
        y_offset = (label_rect.height() - pixmap_rect.height()) / 2

        x = ev.position().x() - x_offset
        y = ev.position().y() - y_offset

        if not (0 <= x < pixmap_rect.width() and 0 <= y < pixmap_rect.height()):
            return

        u = x / pixmap_rect.width()
        v = y / pixmap_rect.height()

        logger.debug(f"Клик по карте мира: u={u:.3f}, v={v:.3f}")
        self.map_clicked.emit(u, v)
        super().mousePressEvent(ev)


class WorldMapWidget(QtWidgets.QWidget):
    generation_requested = QtCore.Signal()

    def __init__(self, main_window: "MainWindow"):
        super().__init__(None)
        self.setWindowTitle("Карта Мира")
        self.setMinimumSize(600, 400)

        self._mw = main_window

        layout = QtWidgets.QVBoxLayout(self)
        self.map_label = InteractiveMapLabel(self)
        layout.addWidget(self.map_label, 1)
        self.progress_bar = QtWidgets.QProgressBar(self)
        self.progress_bar.setVisible(False)
        self.progress_bar.setMaximum(0)
        layout.addWidget(self.progress_bar)
        self.generate_btn = QtWidgets.QPushButton("Обновить Карту")
        self.generate_btn.clicked.connect(self.generation_requested.emit)
        layout.addWidget(self.generate_btn)

    def set_map_pixmap(self, pixmap: QtGui.QPixmap | None):
        if pixmap and not pixmap.isNull():
            scaled_pixmap = pixmap.scaled(
                self.map_label.size(),
                QtCore.Qt.AspectRatioMode.KeepAspectRatio,
                QtCore.Qt.TransformationMode.SmoothTransformation
            )
            self.map_label.setPixmap(scaled_pixmap)
        else:
            self.map_label.setText("Ошибка генерации карты мира")

    def set_busy(self, is_busy: bool):
        self.generate_btn.setEnabled(not is_busy)
        self.progress_bar.setVisible(is_busy)
        if is_busy:
            self.map_label.setText("Генерация...")
