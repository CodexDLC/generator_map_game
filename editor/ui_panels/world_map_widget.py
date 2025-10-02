# editor/ui_panels/world_map_widget.py
from __future__ import annotations
import logging
from typing import TYPE_CHECKING

import numpy as np
from PySide6 import QtWidgets, QtCore, QtGui
from PIL import Image
from PIL.ImageQt import ImageQt

from generator_logic.terrain.global_sphere_noise import global_sphere_noise_wrapper

if TYPE_CHECKING:
    from editor.core.main_window import MainWindow

logger = logging.getLogger(__name__)


class InteractiveMapLabel(QtWidgets.QLabel):
    """ Лейбл, который отлавливает клики мыши и сообщает мировые координаты. """
    region_selected = QtCore.Signal(float, float)  # Сигнал (offset_x, offset_z)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(512, 256)
        self.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.setText("Сгенерируйте карту мира")
        # Сохраняем размер мира из основного UI для правильного расчета смещений
        self._main_world_size_m = 5000.0

    def set_main_world_size(self, world_size_m: float):
        self._main_world_size_m = world_size_m

    def mousePressEvent(self, ev: QtGui.QMouseEvent):
        if not self.pixmap():
            return

        pixmap_rect = self.pixmap().rect()
        label_rect = self.rect()

        x_offset = (label_rect.width() - pixmap_rect.width()) / 2
        y_offset = (label_rect.height() - pixmap_rect.height()) / 2

        x = ev.pos().x() - x_offset
        y = ev.pos().y() - y_offset

        if not (0 <= x < pixmap_rect.width() and 0 <= y < pixmap_rect.height()):
            return

        u = x / pixmap_rect.width()
        v = y / pixmap_rect.height()

        # Карта мира представляет собой диапазон, например, в 4 раза шире текущего вида
        map_width_m = self._main_world_size_m * 4
        map_height_m = self._main_world_size_m * 2

        offset_x = (u - 0.5) * map_width_m
        offset_z = (v - 0.5) * map_height_m * -1  # Инвертируем Z

        logger.info(f"Выбран регион на карте мира. Смещение: X={offset_x:.0f} м, Z={offset_z:.0f} м")
        self.region_selected.emit(offset_x, offset_z)
        super().mousePressEvent(ev)


class WorldMapWidget(QtWidgets.QWidget):
    def __init__(self, main_window: "MainWindow", parent=None):
        super().__init__(parent)
        self.setWindowTitle("Карта Мира")
        self.setMinimumSize(600, 400)

        self._mw = main_window
        self._generation_thread = None

        layout = QtWidgets.QVBoxLayout(self)

        self.map_label = InteractiveMapLabel(self)
        layout.addWidget(self.map_label, 1)

        self.progress_bar = QtWidgets.QProgressBar(self)
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        self.generate_btn = QtWidgets.QPushButton("Сгенерировать/Обновить Карту")
        self.generate_btn.clicked.connect(self.generate_map)
        layout.addWidget(self.generate_btn)

    def generate_map(self):
        """ Запускает генерацию карты в фоновом потоке. """
        self.generate_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.map_label.setText("Генерация...")

        # --- ИСПРАВЛЕНИЕ: Создаем собственный, независимый контекст для карты мира ---
        # Мы больше НЕ вызываем collect_ui_context()
        H, W = 512, 1024  # Фиксированное разрешение для карты мира

        # Создаем пустые координатные сетки. Их значения не важны, важна только форма (shape).
        x_coords, z_coords = np.meshgrid(np.zeros(W, dtype=np.float32), np.zeros(H, dtype=np.float32))

        context = {
            'project': self._mw.project_manager.current_project_data,
            'x_coords': x_coords,
            'z_coords': z_coords,
            'preview_mode': 'Sphere',  # Всегда генерируем всю планету
        }
        # --- КОНЕЦ ИСПРАВЛЕНИЯ ---

        # Собираем параметры шума из главного окна (это правильно)
        sphere_params = {
            'frequency': self._mw.ws_sphere_frequency.value(),
            'octaves': int(self._mw.ws_sphere_octaves.value()),
            'gain': self._mw.ws_sphere_gain.value(),
            'ridge': self._mw.ws_sphere_ridge.isChecked(),
            'seed': self._mw.ws_sphere_seed.value(),
            'ocean_latitude': self._mw.ws_ocean_latitude.value(),
            'ocean_falloff': self._mw.ws_ocean_falloff.value(),
        }

        warp_params = {}  # Для превью карты варп можно отключить, чтобы было быстрее

        # Передаем "Размер мира" для правильного расчета клика
        self.map_label.set_main_world_size(self._mw.world_size_input.value())

        self._generation_thread = GenerationThread(context, sphere_params, warp_params)
        self._generation_thread.result_ready.connect(self.on_map_generated)
        self._generation_thread.start()

    @QtCore.Slot(np.ndarray)
    def on_map_generated(self, noise_map: np.ndarray):
        if noise_map is None:
            self.map_label.setText("Ошибка генерации")
            return

        height, width = noise_map.shape
        image_data = (np.clip(noise_map, 0, 1) * 255).astype(np.uint8)
        pil_img = Image.fromarray(image_data, mode='L')
        q_img = ImageQt(pil_img)
        pixmap = QtGui.QPixmap.fromImage(q_img)

        self.map_label.setPixmap(pixmap.scaled(self.map_label.size(),
                                               QtCore.Qt.AspectRatioMode.KeepAspectRatio,
                                               QtCore.Qt.TransformationMode.SmoothTransformation))

        self.generate_btn.setEnabled(True)
        self.progress_bar.setVisible(False)
        self._generation_thread = None


class GenerationThread(QtCore.QThread):
    """ Поток для выполнения долгой операции генерации шума. """
    result_ready = QtCore.Signal(object)

    def __init__(self, context, sphere_params, warp_params):
        super().__init__()
        self.context = context
        self.sphere_params = sphere_params
        self.warp_params = warp_params

    def run(self):
        try:
            result = global_sphere_noise_wrapper(self.context, self.sphere_params, self.warp_params)
            self.result_ready.emit(result)
        except Exception as e:
            logger.error(f"Ошибка в потоке генерации карты: {e}", exc_info=True)
            self.result_ready.emit(None)