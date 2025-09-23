# ==============================================================================
# Файл: editor/main_window.py
# ВЕРСИЯ 6.0: Полный рефакторинг UI с использованием модульных панелей.
# ==============================================================================

import json
import logging
import time
from pathlib import Path

import numpy as np
from PySide6 import QtWidgets, QtCore, QtGui
from NodeGraphQt import NodeGraph

from .nodes.base_node import GeneratorNode
from .nodes.node_registry import register_all_nodes
from .preview_widget import Preview3DWidget

# --- ACTIONS ---
from .actions.pipeline_actions import on_save_pipeline, on_load_pipeline
from .actions.generation_actions import on_generate_world
from .actions.project_actions import on_save_project

# --- НОВЫЕ ИМПОРТЫ ДЛЯ МОДУЛЬНЫХ ПАНЕЛЕЙ ---
from .ui_panels.project_params_panel import create_project_params_dock
from .ui_panels.global_noise_panel import create_global_noise_dock
from .ui_panels.nodes_palette_panel import create_nodes_palette_dock
from .ui_panels.properties_panel import create_properties_dock
from .ui_panels.compute_panel import create_compute_dock
from .ui_panels.region_presets_panel import create_region_presets_dock

logger = logging.getLogger(__name__)


class MainWindow(QtWidgets.QMainWindow):
    # --- Слоты для сигналов от воркеров (без изменений) ---
    @QtCore.Slot(int, int, object, int, int, float)
    def on_tile_ready(self, tx, tz, tile, cs, rs, cell_size):
        """
        Слот, который получает готовый тайл от воркера.
        """
        # --- НАЧАЛО ИСПРАВЛЕНИЯ ---
        # 1. Преобразуем полученный объект в numpy массив
        tile_np = np.asarray(tile, dtype=np.float32)

        # 2. Проводим валидацию
        if tile_np.ndim != 2 or not np.isfinite(tile_np).all():
            self.statusBar.showMessage(f"Пропущен плохой тайл ({tx},{tz})", 2000)
            return
        # --- КОНЕЦ ИСПРАВЛЕНИЯ ---

        # Сохраняем тайл в словарь для последующей сборки
        self.tiled_results[(tx, tz)] = tile_np

        # Сохраняем параметры генерации (на случай, если они изменятся)
        if not self.tiled_params:
            self.tiled_params = {'cs': cs, 'rs': rs, 'cell_size': cell_size}

        # Отправляем тайл на "прогрессивную" отрисовку, как и раньше
        self.preview_widget.on_tile_ready(tx, tz, tile_np, cs, rs, cell_size)

    @QtCore.Slot(str)
    def on_tiled_compute_finished(self, message):
        """Слот, который вызывается ТОЛЬКО по завершении тайловой генерации."""
        logger.info(f"Tiled compute finished: {message}")

        # --- НАЧАЛО ИЗМЕНЕНИЙ: Логика сборки холста ---
        try:
            logger.info("Stitching tiles into a single heightmap...")
            if not self.tiled_results or not self.tiled_params:
                logger.warning("No tiles were generated or params are missing. Skipping stitch.")
                return

            cs = self.tiled_params['cs']
            rs = self.tiled_params['rs']
            cell_size = self.tiled_params['cell_size']

            # Создаем большой пустой массив для всего региона
            # Важно: мы не используем "фартук" (+1) для финального холста
            full_heightmap = np.zeros((rs * cs, rs * cs), dtype=np.float32)

            # Собираем все тайлы в один большой массив
            for (tx, tz), tile_data in self.tiled_results.items():
                # Обрезаем "фартук" (+1 пиксель) с каждого тайла
                tile_core = tile_data[:-1, :-1]

                # Вычисляем позицию и вставляем в большой массив
                x_offset = tx * cs
                z_offset = tz * cs
                full_heightmap[z_offset:z_offset + cs, x_offset:x_offset + cs] = tile_core

            logger.info(f"Stitching complete. Final heightmap shape: {full_heightmap.shape}")

            # Отправляем собранный холст в 3D-вьювер для финальной отрисовки
            self.preview_widget.update_mesh(full_heightmap, cell_size)
            self.statusBar.showMessage("Сборка тайлов завершена.", 5000)

        except Exception as e:
            logger.exception("Failed to stitch tiles.")
            self.on_compute_error(f"Ошибка сборки тайлов: {e}")
        finally:
            # Очищаем кэш для следующего запуска
            self.tiled_results.clear()
            self.tiled_params.clear()

    @QtCore.Slot(object, str)
    def on_compute_finished(self, result, message):
        logger.info(f"Single compute finished: {message}")
        if result is None:
            logger.warning("Received None result. Graph connection might be broken.")
            self.statusBar.showMessage("Пустой результат (None). Проверь соединения графа.", 6000)
            return

        try:
            arr = np.asarray(result, dtype=np.float32)
            if arr.ndim != 2 or not np.isfinite(arr).all():
                logger.error(f"Invalid result format. Shape: {arr.shape}, Has NaN/Inf: {not np.isfinite(arr).all()}")
                self.statusBar.showMessage("Неверный формат результата (ожидается 2D, без NaN/Inf).", 6000)
                return

            # Берём текущий cell_size из UI
            cell_size = float(self.cell_size_input.value())
            logger.debug(f"Updating preview mesh with shape {arr.shape} and cell_size {cell_size}")
            self.preview_widget.update_mesh(arr, cell_size)
            self.statusBar.showMessage(message or "Готово", 4000)
        except Exception as e:
            logger.exception("Error processing final result in on_compute_finished.")
            self.on_compute_error(str(e))

    @QtCore.Slot(str)
    def on_compute_error(self, message):
        logger.error(f"Compute error: {message}")
        QtWidgets.QMessageBox.critical(self, "Ошибка вычисления", str(message))
        self.statusBar.showMessage(f"Ошибка: {message.splitlines()[0]}", 6000)

    # --- Обновленный конструктор и методы ---
    def __init__(self, project_path: str):
        super().__init__()
        logger.info("Initializing MainWindow with layered architecture...")
        self.current_project_path = project_path

        # --- АТРИБУТЫ ДЛЯ МНОЖЕСТВА ГРАФОВ ---
        self.graphs = {}
        self.tab_widget = QtWidgets.QTabWidget()
        self._init_ui_attributes()

        project_data = self.get_project_data()
        if not project_data:
            QtWidgets.QMessageBox.critical(self, "Ошибка проекта", f"Не удалось загрузить данные из {project_path}")
            QtCore.QTimer.singleShot(0, self.close)
            return

        self.setWindowTitle("Редактор Миров")
        self.resize(1600, 900)

        # --- СОЗДАНИЕ ЦЕНТРАЛЬНОГО ВИДЖЕТА С ВКЛАДКАМИ ---
        self._setup_central_widget_with_tabs()

        # --- ИНИЦИАЛИЗАЦИЯ ---
        self._setup_docks()
        self._setup_menu()
        self.statusBar = QtWidgets.QStatusBar()
        self.setStatusBar(self.statusBar)

        # Связываем изменение свойств с кэшированием
        for graph in self.graphs.values():
            graph.property_changed.connect(self._on_node_property_changed)

        self._apply_project_to_ui(project_data)
        self.statusBar.showMessage(f"Проект загружен: {project_path}", 5000)

    def _init_ui_attributes(self):
        """Инициализирует все атрибуты UI и состояния в None или пустые значения."""
        # Панель "Пресеты Региона"
        self.presets_list_widget = None

        # Панели "Палитра Нодов" и "Свойства Нода" (для переключения контекста)
        self.dock_nodes = None
        self.dock_props = None

        # Панель "Параметры Проекта"
        self.seed_input = None
        self.global_x_offset_input = None
        self.global_z_offset_input = None
        self.chunk_size_input = None
        self.region_size_input = None
        self.cell_size_input = None
        self.total_size_label = None

        # Панель "Глобальный Шум"
        self.gn_scale_input = None
        self.gn_octaves_input = None
        self.gn_amp_input = None
        self.gn_ridge_checkbox = None

        # Панель "Вычисление"
        self.apply_button = None
        self.apply_tiled_button = None

        # Асинхронные операции и состояние
        self.thread = None
        self.worker = None
        self.tiled_results = {}
        self.tiled_params = {}

    def get_active_graph(self) -> NodeGraph | None:
        """Возвращает объект графа из активной вкладки."""
        current_widget = self.tab_widget.currentWidget()
        if current_widget:
            return current_widget.property("graph_instance")
        return None

    def _setup_central_widget_with_tabs(self):
        """Создает вкладки и помещает в них графы."""
        layer_names = ["Ландшафт", "Климат (Заглушка)", "Биомы (Заглушка)"]
        for name in layer_names:
            graph = NodeGraph()

            # --- НАЧАЛО ИСПРАВЛЕНИЯ ---
            # 1. СНАЧАЛА регистрируем все ноды для этого конкретного экземпляра графа.
            register_all_nodes(graph)
            # --- КОНЕЦ ИСПРАВЛЕНИЯ ---

            self.graphs[name] = graph

            graph_widget = graph.widget
            graph_widget.setProperty("graph_instance", graph)

            # Создаем ноды по умолчанию
            # TODO: Создать специальные ноды Input/Output для каждого слоя
            # 2. ТЕПЕРЬ можно безопасно создавать ноды.
            graph.create_node('generator.pipeline.WorldInputNode', name='Вход', pos=(-300, 0))
            graph.create_node('generator.pipeline.OutputNode', name='Выход', pos=(100, 0))

            self.tab_widget.addTab(graph_widget, name)


        # Splitter для 3D-превью и вкладок с графами
        splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Vertical)
        self.preview_widget = Preview3DWidget()
        splitter.addWidget(self.preview_widget)
        splitter.addWidget(self.tab_widget)
        splitter.setSizes([400, 600])
        self.setCentralWidget(splitter)

    def closeEvent(self, e):
        logger.info("Close event triggered. Quitting all QThreads.")
        for th in self.findChildren(QtCore.QThread):
            th.quit()
            th.wait(2000)
        super().closeEvent(e)


    def _setup_docks(self):
        self.setDockNestingEnabled(True)
        # --- ИЗМЕНЕНИЕ: Убираем отсюда создание панелей, зависящих от графа ---
        create_region_presets_dock(self)
        # create_nodes_palette_dock(self) # <-- УДАЛЯЕМ
        create_project_params_dock(self)
        create_global_noise_dock(self)
        # create_properties_dock(self) # <-- УДАЛЯЕМ
        create_compute_dock(self)

        # --- ИЗМЕНЕНИЕ: Вся логика теперь в обработчике смены вкладок ---
        self.tab_widget.currentChanged.connect(self._on_tab_changed)
        # Вызываем один раз для инициализации панелей для первой вкладки
        self._on_tab_changed()

    def _on_tab_changed(self):
        """
        Полностью пересоздает панели, зависящие от графа, при смене вкладки.
        Это единственно надежный способ работы с NodeGraphQt.
        """
        # --- НАЧАЛО НОВОЙ ЛОГИКИ ---

        # 1. Удаляем старые док-виджеты, если они существуют
        if self.dock_nodes:
            self.removeDockWidget(self.dock_nodes)
            self.dock_nodes.deleteLater()
            self.dock_nodes = None
        if self.dock_props:
            self.removeDockWidget(self.dock_props)
            self.dock_props.deleteLater()
            self.dock_props = None

        # 2. Создаем новые док-виджеты, которые будут автоматически
        #    привязаны к текущему активному графу.
        create_nodes_palette_dock(self)
        create_properties_dock(self)

        # Восстанавливаем расположение панелей (опционально, для удобства)
        self.tabifyDockWidget(self.dock_region_presets, self.dock_nodes)
        self.tabifyDockWidget(self.dock_project_params, self.dock_global_noise)
        self.tabifyDockWidget(self.dock_global_noise, self.dock_props)

    def _on_node_property_changed(self, node, prop_name, prop_value):
        """Когда свойство ноды меняется, помечаем ее как 'грязную'."""

        logger.debug(f"Node '{node.name()}' property '{prop_name}' changed. Marking as dirty.")
        if isinstance(node, GeneratorNode):
            node.mark_dirty()

    def _setup_menu(self):
        # ... (метод обновлен для соответствия ТЗ) ...
        m = self.menuBar()
        proj = m.addMenu("Проект")
        proj.addAction("Сохранить Проект").triggered.connect(self.on_save_project)
        proj.addSeparator()
        proj.addAction("Сгенерировать Мир...").triggered.connect(lambda: on_generate_world(self))
        proj.addSeparator()
        proj.addAction("Выход").triggered.connect(self.close)

        layers = m.addMenu("Слои")
        layers.addAction("Загрузить Пресет в новый Слой...").triggered.connect(lambda: on_load_pipeline(self))
        layers.addAction("Сохранить текущий Слой как Пресет...").triggered.connect(lambda: on_save_pipeline(self))

    def get_project_data(self):
        # ... (без изменений) ...
        if not self.current_project_path: return None
        try:
            with open(Path(self.current_project_path) / "project.json", "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            self.statusBar.showMessage(f"Ошибка чтения файла проекта: {e}", 5000)
            return None

    def _apply_project_to_ui(self, data: dict) -> None:
        """Загружает данные из project.json во все панели."""
        # --- Основные параметры ---
        self.seed_input.setValue(int(data.get("seed", 1)))
        self.chunk_size_input.setValue(int(data.get("chunk_size", 128)))
        self.region_size_input.setValue(int(data.get("region_size_in_chunks", 4)))
        self.cell_size_input.setValue(float(data.get("cell_size", 1.0)))
        self.global_x_offset_input.setValue(int(data.get("global_x_offset", 0.0)))
        self.global_z_offset_input.setValue(int(data.get("global_z_offset", 0.0)))

        # --- Параметры глобального шума ---
        noise_data = data.get("global_noise", {})
        self.gn_scale_input.setValue(float(noise_data.get("scale_tiles", 6000.0)))
        self.gn_octaves_input.setValue(int(noise_data.get("octaves", 3)))
        self.gn_amp_input.setValue(float(noise_data.get("amp_m", 400.0)))
        self.gn_ridge_checkbox.setChecked(bool(noise_data.get("ridge", False)))

        # Обновление заголовка
        project_name = data.get("project_name", "Безымянный проект")
        self.setWindowTitle(f"Редактор Миров — [{project_name}]")

    def on_save_project(self):
        """Прокси-метод для вызова сохранения проекта."""
        on_save_project(self)

    def _ensure_graph_focus(self):
        # ... (без изменений) ...
        viewer = self.graph.widget
        viewer.setFocusPolicy(QtCore.Qt.FocusPolicy.StrongFocus)
        if not viewer.hasFocus():
            viewer.setFocus(QtCore.Qt.FocusReason.ActiveWindowFocusReason)

    def _delete_selected_nodes(self):
        # ... (без изменений) ...
        selected = self.graph.selected_nodes()
        if selected:
            self.graph.delete_nodes(selected)

