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

from .actions.preset_actions import load_preset_into_graphs, create_new_preset_files
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

        self.setTabPosition(
            QtCore.Qt.DockWidgetArea.AllDockWidgetAreas,
            QtWidgets.QTabWidget.TabPosition.North
        )

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
        self._load_presets_list()
        self.statusBar.showMessage(f"Проект загружен: {project_path}", 5000)



    def _init_ui_attributes(self):
        """Инициализирует все атрибуты UI и состояния в None или пустые значения."""
        # Панель "Пресеты Региона"
        self.presets_list_widget = None

        self.dock_region_presets = None
        self.dock_nodes = None
        self.dock_props = None
        self.dock_project_params = None
        self.dock_global_noise = None

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

        self.wants_restart = False

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
            register_all_nodes(graph)

            self.graphs[name] = graph
            graph_widget = graph.widget
            graph_widget.setProperty("graph_instance", graph)

            delete_shortcut = QtGui.QShortcut(QtGui.QKeySequence(QtCore.Qt.Key.Key_Delete), graph_widget)
            delete_shortcut.setContext(QtCore.Qt.ShortcutContext.WidgetShortcut)
            delete_shortcut.activated.connect(self._delete_selected_nodes)

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

        m = self.menuBar()
        proj = m.addMenu("Проект")

        def return_to_manager():
            self.wants_restart = True
            self.close()

        proj.addAction("Сменить проект...").triggered.connect(return_to_manager)
        proj.addSeparator()

        proj.addAction("Сохранить Проект").triggered.connect(self.on_save_project)
        proj.addSeparator()
        proj.addAction("Сгенерировать Мир...").triggered.connect(lambda: on_generate_world(self))
        proj.addSeparator()
        proj.addAction("Выход").triggered.connect(self.close)

        layers = m.addMenu("Пресеты регионов")
        layers.addAction("Загрузить Пресет").triggered.connect(lambda: on_load_pipeline(self))
        layers.addAction("Сохранить Пресет...").triggered.connect(lambda: on_save_pipeline(self))

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

        viewer = self.graph.widget
        viewer.setFocusPolicy(QtCore.Qt.FocusPolicy.StrongFocus)
        if not viewer.hasFocus():
            viewer.setFocus(QtCore.Qt.FocusReason.ActiveWindowFocusReason)

    def _delete_selected_nodes(self):
        """Удаляет выделенные ноды из АКТИВНОГО графа."""
        active_graph = self.get_active_graph()
        if not active_graph:
            return

        selected_nodes = active_graph.selected_nodes()
        if selected_nodes:
            active_graph.delete_nodes(selected_nodes)

    def _load_presets_list(self):
        """Читает project.json, заполняет список и выбирает активный пресет."""
        # Временно отключаем сигнал, чтобы не вызывать on_preset_selected во время заполнения
        self.presets_list_widget.currentItemChanged.disconnect(self.on_preset_selected)

        self.presets_list_widget.clear()
        project_data = self.get_project_data()
        presets = project_data.get("region_presets", {})

        active_preset_name = project_data.get("active_preset_name", "")
        item_to_select = None

        for name in presets.keys():
            item = QtWidgets.QListWidgetItem(name)
            self.presets_list_widget.addItem(item)
            if name == active_preset_name:
                item_to_select = item

        # Включаем сигнал обратно
        self.presets_list_widget.currentItemChanged.connect(self.on_preset_selected)

        # Выбираем нужный элемент в списке, что вызовет on_preset_selected
        if item_to_select:
            self.presets_list_widget.setCurrentItem(item_to_select)
        elif self.presets_list_widget.count() > 0:
            self.presets_list_widget.setCurrentRow(0)

    def _update_preset_list_font(self):
        """Обновляет шрифт в списке, делая активный пресет жирным."""
        project_data = self.get_project_data()
        active_preset_name = project_data.get("active_preset_name", "")
        for i in range(self.presets_list_widget.count()):
            item = self.presets_list_widget.item(i)
            font = item.font()
            is_active = (item.text() == active_preset_name)
            font.setBold(is_active)
            item.setFont(font)

    def on_preset_selected(self, current_item: QtWidgets.QListWidgetItem, previous_item: QtWidgets.QListWidgetItem):
        """Загружает выбранный пресет и обновляет UI."""
        if not current_item:
            return

        preset_name = current_item.text()
        logger.info(f"Preset selected: {preset_name}")
        project_data = self.get_project_data()

        # 1. Запоминаем выбор как активный
        project_data["active_preset_name"] = preset_name

        # 2. Обновляем шрифт в списке
        self._update_preset_list_font()

        # 3. Загружаем графы
        preset_info = project_data.get("region_presets", {}).get(preset_name)
        if not preset_info:
            logger.error(f"Preset '{preset_name}' not found in project.json")
            return

        load_preset_into_graphs(self, preset_info)
        self.statusBar.showMessage(f"Пресет '{preset_name}' загружен", 4000)



    def on_new_preset_clicked(self):
        """Вызывается при нажатии кнопки [+] на панели пресетов."""
        preset_name, ok = QtWidgets.QInputDialog.getText(self, "Новый пресет", "Введите имя пресета:")
        if not (ok and preset_name.strip()):
            return

        preset_name = preset_name.strip()
        project_data = self.get_project_data()

        # Проверяем, существует ли уже пресет с таким именем
        if preset_name in project_data.get("region_presets", {}):
            QtWidgets.QMessageBox.warning(self, "Ошибка", "Пресет с таким именем уже существует.")
            return

        # Создаем информацию о файлах для нового пресета
        preset_info = {
            "description": "Новый пресет",
            "landscape_graph": f"pipelines/{preset_name}_landscape.json",
            "climate_graph": f"pipelines/{preset_name}_climate.json",
            "biome_graph": f"pipelines/{preset_name}_biome.json"
        }

        # Создаем пустые .json файлы
        pipelines_dir = Path(self.current_project_path) / "pipelines"
        pipelines_dir.mkdir(exist_ok=True)
        empty_graph_data = {"nodes": {}, "connections": []}
        for key in ["landscape_graph", "climate_graph", "biome_graph"]:
            file_path = Path(self.current_project_path) / preset_info[key]
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(empty_graph_data, f)

        # --- НАЧАЛО ИСПРАВЛЕНИЯ ---
        # Убеждаемся, что словарь для пресетов существует, прежде чем добавлять в него.
        if "region_presets" not in project_data:
            project_data["region_presets"] = {}
        # --- КОНЕЦ ИСПРАВЛЕНИЯ ---

        # Обновляем project.json
        project_data["region_presets"][preset_name] = preset_info
        on_save_project(self, project_data)  # Сохраняем изменения

        # Обновляем список в UI
        self._load_presets_list()
        self.statusBar.showMessage(f"Пресет '{preset_name}' создан.", 4000)


    def on_delete_preset_clicked(self):
        """Удаляет выбранный пресет и его файлы."""
        selected_items = self.presets_list_widget.selectedItems()
        if not selected_items:
            self.statusBar.showMessage("Сначала выберите пресет для удаления.", 3000)
            return

        preset_name = selected_items[0].text()
        if preset_name == "default":
            QtWidgets.QMessageBox.warning(self, "Ошибка", "Пресет 'default' нельзя удалить.")
            return

        reply = QtWidgets.QMessageBox.question(self, "Подтверждение",
                                               f"Вы уверены, что хотите удалить пресет '{preset_name}'?\n"
                                               f"Это действие необратимо.",
                                               QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No)
        if reply == QtWidgets.QMessageBox.StandardButton.No:
            return

        project_data = self.get_project_data()
        presets = project_data.get("region_presets", {})
        preset_to_delete = presets.pop(preset_name, None)

        if preset_to_delete:
            # Удаляем файлы графов с диска
            project_path = Path(self.current_project_path)
            for key in ["landscape_graph", "climate_graph", "biome_graph"]:
                try:
                    file_path = project_path / preset_to_delete[key]
                    if file_path.exists():
                        file_path.unlink()
                        logger.info(f"Deleted preset file: {file_path}")
                except Exception as e:
                    logger.error(f"Could not delete file {file_path}: {e}")

        # Если мы удалили активный пресет, делаем активным 'default'
        if project_data.get("active_preset_name") == preset_name:
            project_data["active_preset_name"] = "default"

        on_save_project(self, project_data) # Сохраняем изменения в project.json
        self._load_presets_list() # Обновляем список в UI
        self.statusBar.showMessage(f"Пресет '{preset_name}' удален.", 4000)