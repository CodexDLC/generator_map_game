# ==============================================================================
# Файл: editor/main_window.py
# ВЕРСИЯ 6.0: Полный рефакторинг UI с использованием модульных панелей.
# ==============================================================================

import json
from pathlib import Path

from PySide6 import QtWidgets, QtCore, QtGui
from NodeGraphQt import NodeGraph

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


class MainWindow(QtWidgets.QMainWindow):
    # --- Слоты для сигналов от воркеров (без изменений) ---
    @QtCore.Slot(int, int, object)
    def on_tile_ready(self, tx, tz, tile):
        import numpy as np
        t = np.asarray(tile, dtype=np.float32)
        if t.ndim != 2 or not np.isfinite(t).all():
            self.statusBar.showMessage(f"Пропущен плохой тайл ({tx},{tz})", 2000)
            return
        cs = self.chunk_size_input.value()
        rs = self.region_size_input.value()
        cell = self.cell_size_input.value()
        self.preview_widget.on_tile_ready(tx, tz, t, cs, rs, cell)

    @QtCore.Slot(object, str)
    def on_compute_finished(self, result, message):
        import numpy as np
        if result is not None:
            cell = float(self.cell_size_input.value())
            self.preview_widget.update_mesh(result, cell)
        self.statusBar.showMessage(message, 4000)

    @QtCore.Slot(str)
    def on_compute_error(self, message):
        print(f"[TRACE/UI] on_compute_error: {message}", flush=True)
        QtWidgets.QMessageBox.critical(self, "Ошибка вычисления", str(message))
        self.statusBar.showMessage(f"Ошибка: {message.splitlines()[0]}", 6000)

    # --- Обновленный конструктор и методы ---
    def __init__(self, project_path: str):
        super().__init__()
        self.graph = NodeGraph()
        self.current_project_path = project_path

        project_data = self.get_project_data()
        if not project_data:
            QtWidgets.QMessageBox.critical(self, "Ошибка проекта", f"Не удалось загрузить данные из {project_path}")
            QtCore.QTimer.singleShot(0, self.close)
            return

        self.setWindowTitle("Редактор Миров")
        self.resize(1600, 900)

        # --- Центральная область (без изменений) ---
        graph_widget = self.graph.widget
        graph_widget.setFocusPolicy(QtCore.Qt.FocusPolicy.StrongFocus)
        delete_sc = QtGui.QShortcut(QtGui.QKeySequence(QtCore.Qt.Key_Delete), graph_widget)
        delete_sc.setContext(QtCore.Qt.ShortcutContext.WidgetWithChildrenShortcut)
        delete_sc.activated.connect(self._delete_selected_nodes)
        central = QtWidgets.QWidget()
        v = QtWidgets.QVBoxLayout(central);
        v.setContentsMargins(0, 0, 0, 0);
        v.setSpacing(0)
        splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Vertical)
        self.preview_widget = Preview3DWidget()
        splitter.addWidget(self.preview_widget)
        splitter.addWidget(graph_widget)
        splitter.setSizes([420, 680])
        v.addWidget(splitter)
        self.setCentralWidget(central)
        self._ensure_graph_focus()
        QtCore.QTimer.singleShot(0, self._ensure_graph_focus)

        # --- Инициализация компонентов ---
        register_all_nodes(self.graph)
        self._setup_docks()
        self._setup_menu()
        self.statusBar = QtWidgets.QStatusBar()
        self.setStatusBar(self.statusBar)

        # Загружаем данные из project.json в созданные панели
        self._apply_project_to_ui(project_data)
        self.statusBar.showMessage(f"Проект загружен: {project_path}", 5000)

    def closeEvent(self, e):
        # ... (без изменений) ...
        print("[TRACE/UI] closeEvent: quitting all QThreads", flush=True)
        for th in self.findChildren(QtCore.QThread):
            th.quit()
            th.wait(2000)
        super().closeEvent(e)

    def _setup_docks(self):
        """
        Инициализирует все док-виджеты, вызывая функции из модулей.
        Этот метод стал намного чище и короче.
        """
        self.setDockNestingEnabled(True)

        # Создаем и добавляем каждую панель, вызывая соответствующую функцию
        create_nodes_palette_dock(self)
        create_project_params_dock(self)
        create_global_noise_dock(self)
        create_properties_dock(self)
        create_compute_dock(self)

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
        self.global_x_offset_input.setValue(float(data.get("global_x_offset", 0.0)))
        self.global_z_offset_input.setValue(float(data.get("global_z_offset", 0.0)))

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