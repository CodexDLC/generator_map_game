# editor/ui/layouts/world_map_window.py
from __future__ import annotations
import logging
from typing import TYPE_CHECKING

from PySide6 import QtWidgets, QtCore, QtGui

if TYPE_CHECKING:
    from editor.core.main_window import MainWindow

logger = logging.getLogger(__name__)


class InteractiveMapView(QtWidgets.QGraphicsView):
    """
    Виджет для отображения карты с поддержкой масштабирования (зум)
    и панорамирования (перемещение).
    """
    map_clicked = QtCore.Signal(float, float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTransformationAnchor(QtWidgets.QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QtWidgets.QGraphicsView.AnchorViewCenter)
        self.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.setDragMode(QtWidgets.QGraphicsView.ScrollHandDrag)
        self.setRenderHint(QtGui.QPainter.Antialiasing)

        self._scene = QtWidgets.QGraphicsScene(self)
        self.setScene(self._scene)
        self._pixmap_item = QtWidgets.QGraphicsPixmapItem()
        self._scene.addItem(self._pixmap_item)

    def set_pixmap(self, pixmap: QtGui.QPixmap | None):
        if pixmap and not pixmap.isNull():
            self._pixmap_item.setPixmap(pixmap)
            self.fitInView(self._pixmap_item, QtCore.Qt.AspectRatioMode.KeepAspectRatio)
        else:
            # Можно добавить заглушку, если нужно
            self._pixmap_item.setPixmap(QtGui.QPixmap())

    def wheelEvent(self, event: QtGui.QWheelEvent):
        """Обрабатывает масштабирование колесом мыши."""
        zoom_in_factor = 1.25
        zoom_out_factor = 1 / zoom_in_factor

        if event.angleDelta().y() > 0:
            self.scale(zoom_in_factor, zoom_in_factor)
        else:
            self.scale(zoom_out_factor, zoom_out_factor)

    def mousePressEvent(self, event: QtGui.QMouseEvent):
        """Перехватывает клик для определения координат."""
        if self._pixmap_item.pixmap().isNull():
            super().mousePressEvent(event)
            return

        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            # Преобразуем координаты клика в координаты сцены, а затем в координаты картинки
            scene_pos = self.mapToScene(event.pos())
            pixmap_pos = self._pixmap_item.mapFromScene(scene_pos)

            pixmap = self._pixmap_item.pixmap()
            if pixmap.rect().contains(pixmap_pos.toPoint()):
                u = pixmap_pos.x() / pixmap.width()
                v = pixmap_pos.y() / pixmap.height()
                self.map_clicked.emit(u, v)

        # Передаем событие дальше для стандартной обработки (например, для панорамирования)
        super().mousePressEvent(event)


class WorldMapWidget(QtWidgets.QWidget):
    """
    Виджет-контейнер для интерактивной карты и кнопки обновления.
    """
    generation_requested = QtCore.Signal()

    def __init__(self, main_window: "MainWindow"):
        super().__init__(None)
        self.setWindowTitle("Карта Мира")

        self._mw = main_window

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self.map_view = InteractiveMapView(self)
        layout.addWidget(self.map_view, 1)

        bottom_bar = QtWidgets.QHBoxLayout()
        bottom_bar.setContentsMargins(8, 0, 8, 8)
        self.progress_bar = QtWidgets.QProgressBar(self)
        self.progress_bar.setVisible(False)
        self.progress_bar.setMaximum(0)
        bottom_bar.addWidget(self.progress_bar)

        self.generate_btn = QtWidgets.QPushButton("Обновить Карту")
        self.generate_btn.clicked.connect(self.generation_requested.emit)
        bottom_bar.addWidget(self.generate_btn)

        layout.addLayout(bottom_bar)

    def set_map_pixmap(self, pixmap: QtGui.QPixmap | None):
        self.map_view.set_pixmap(pixmap)

    def set_busy(self, is_busy: bool):
        self.generate_btn.setEnabled(not is_busy)
        self.progress_bar.setVisible(is_busy)
        if is_busy and (self.map_view._pixmap_item.pixmap() is None or self.map_view._pixmap_item.pixmap().isNull()):
            # Показываем текст "Генерация..." только если карты еще нет
            pass  # В QGraphicsView нет простого способа показать текст поверх