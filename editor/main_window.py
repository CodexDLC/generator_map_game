# ==============================================================================
# Файл: editor/main_window.py
# ВЕРСИЯ 5.1: Слоты для безопасных UI-апдейтов из воркеров + аккуратные доки.
# ==============================================================================

import json
from pathlib import Path

from typing import cast

from PySide6 import QtWidgets, QtCore, QtGui
from NodeGraphQt import NodesTreeWidget, PropertiesBinWidget, NodeGraph

from .nodes.node_registry import register_all_nodes
from .preview_widget import Preview3DWidget


# actions
from .actions.project_actions import on_new_project, on_open_project
from .actions.pipeline_actions import on_save_pipeline, on_load_pipeline
from .actions.generation_actions import on_generate_world
from .actions.compute_actions import on_apply_clicked, on_apply_tiled_clicked



class MainWindow(QtWidgets.QMainWindow):
    # Слоты, чтобы получать сигналы из фоновых воркеров «в очередь»


    @QtCore.Slot(int, int, object)
    def on_tile_ready(self, tx, tz, tile):
        # Этот слот получает тайлы от TiledComputeWorker
        import numpy as np
        t = np.asarray(tile, dtype=np.float32)
        if t.ndim != 2 or not np.isfinite(t).all():
            self.statusBar.showMessage(f"Пропущен плохой тайл ({tx},{tz})", 2000)
            return

        # ---> НАЧАЛО ИЗМЕНЕНИЙ <---
        # Получаем актуальные параметры из UI
        cs = self.chunk_size_input.value()
        rs = self.region_size_input.value()
        cell = self.cell_size_input.value()

        # Вызываем обновленный метод виджета с дополнительными параметрами
        self.preview_widget.on_tile_ready(tx, tz, t, cs, rs, cell)
        # ---> КОНЕЦ ИЗМЕНЕНИЙ <---

    @QtCore.Slot(object, str)
    def on_compute_finished(self, result, message):
        # Этот слот вызывается от ОБОИХ воркеров
        import numpy as np

        # Если result не пустой, значит это был ОДИНОЧНЫЙ рендер (кнопка APPLY)
        # TiledComputeWorker в конце присылает result=None
        if result is not None:
            cell = float(self.cell_size_input.value())
            # Вызываем исправленный update_mesh
            self.preview_widget.update_mesh(result, cell)

        self.statusBar.showMessage(message, 4000)

    @QtCore.Slot(str)
    def on_compute_error(self, message):
        print(f"[TRACE/UI] on_compute_error: {message}", flush=True)
        QtWidgets.QMessageBox.critical(self, "Ошибка вычисления", str(message))
        # НИЧЕГО не делаем с preview_widget: оставляем текущую картинку как есть
        self.statusBar.showMessage(f"Ошибка: {message.splitlines()[0]}", 6000)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Редактор Миров")
        self.resize(1600, 900)

        self.graph = NodeGraph()
        self.current_project_path = None

        # --- центральная область: сверху превью, снизу граф ---
        graph_widget = self.graph.widget
        graph_widget.setFocusPolicy(QtCore.Qt.FocusPolicy.StrongFocus)
        delete_sc = QtGui.QShortcut(QtGui.QKeySequence(QtCore.Qt.Key_Delete), graph_widget)
        delete_sc.setContext(QtCore.Qt.ShortcutContext.WidgetWithChildrenShortcut)
        delete_sc.activated.connect(self._delete_selected_nodes)

        back_sc = QtGui.QShortcut(QtGui.QKeySequence(QtCore.Qt.Key_Backspace), graph_widget)
        back_sc.setContext(QtCore.Qt.ShortcutContext.WidgetWithChildrenShortcut)
        back_sc.activated.connect(self._delete_selected_nodes)

        central = QtWidgets.QWidget()
        v = QtWidgets.QVBoxLayout(central); v.setContentsMargins(0, 0, 0, 0); v.setSpacing(0)
        splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Vertical)
        self.preview_widget = Preview3DWidget()
        self.preview_widget.setMinimumHeight(220)
        splitter.addWidget(self.preview_widget)
        splitter.addWidget(graph_widget)
        splitter.setSizes([420, 680])
        v.addWidget(splitter)
        self.setCentralWidget(central)

        self._ensure_graph_focus()
        QtCore.QTimer.singleShot(0, self._ensure_graph_focus)

        # Delete — используем встроенную обработку NodeGraphQt.
        # Никаких QShortcut/QAction сверху не навешиваем, чтобы не было конфликтов.

        # реестр нод
        register_all_nodes(self.graph)

        # доки
        self._setup_docks()

        # меню
        self._setup_menu()

        # статусбар
        self.statusBar = QtWidgets.QStatusBar()
        self.setStatusBar(self.statusBar)

    def closeEvent(self, e):
        print("[TRACE/UI] closeEvent: quitting all QThreads", flush=True)
        for th in self.findChildren(QtCore.QThread):
            th.quit();
            th.wait(2000)
        super().closeEvent(e)


    # --------------------------- UI компоновка ---------------------------------
    def _setup_docks(self):
        self.setDockNestingEnabled(True)

        # --- Палитра ---
        nodes_tree = NodesTreeWidget(node_graph=self.graph)
        self.dock_nodes = QtWidgets.QDockWidget("Палитра Нодов", self)
        # setWidget ждёт QWidget — NodesTreeWidget им и является.
        # IDE тупит, поэтому можно явно "кастануть" для тишины:
        self.dock_nodes.setWidget(cast(QtWidgets.QWidget, nodes_tree))
        self.addDockWidget(QtCore.Qt.DockWidgetArea.LeftDockWidgetArea, self.dock_nodes)

        # --- Настройки ---
        settings = QtWidgets.QWidget()
        form = QtWidgets.QFormLayout(settings)

        self.seed_input = QtWidgets.QSpinBox(minimum=0, maximum=999_999)
        self.seed_input.setValue(12345)
        form.addRow("World Seed:", self.seed_input)

        self.global_x_offset_input = QtWidgets.QSpinBox(minimum=-999_999, maximum=999_999)
        self.global_x_offset_input.setSingleStep(512)
        self.global_x_offset_input.setValue(0)
        form.addRow("Global X Offset:", self.global_x_offset_input)

        self.global_z_offset_input = QtWidgets.QSpinBox(minimum=-999_999, maximum=999_999)
        self.global_z_offset_input.setSingleStep(512)
        self.global_z_offset_input.setValue(0)
        form.addRow("Global Z Offset:", self.global_z_offset_input)

        self.chunk_size_input = QtWidgets.QSpinBox(minimum=64, maximum=1024)
        self.chunk_size_input.setValue(512)
        form.addRow("Chunk Size (px):", self.chunk_size_input)

        self.region_size_input = QtWidgets.QSpinBox(minimum=1, maximum=32)
        self.region_size_input.setValue(1)
        form.addRow("Region Size (chunks):", self.region_size_input)

        self.cell_size_input = QtWidgets.QDoubleSpinBox(minimum=0.1, maximum=10.0, decimals=2)
        self.cell_size_input.setSingleStep(0.1)
        self.cell_size_input.setValue(1.0)
        form.addRow("Cell Size (m):", self.cell_size_input)

        self.dock_settings = QtWidgets.QDockWidget("Настройки", self)
        self.dock_settings.setWidget(settings)
        self.addDockWidget(QtCore.Qt.DockWidgetArea.RightDockWidgetArea, self.dock_settings)

        # --- Инспектор + APPLY ---
        props_bin = PropertiesBinWidget(node_graph=self.graph)
        props_wrap = QtWidgets.QWidget()
        v = QtWidgets.QVBoxLayout(props_wrap)
        v.setContentsMargins(0, 0, 0, 0)
        self.apply_button = QtWidgets.QPushButton("APPLY")
        self.apply_button.setFixedHeight(40)

        self.apply_button.clicked.connect(lambda: on_apply_clicked(self))

        self.apply_tiled_button = QtWidgets.QPushButton("APPLY (tiled)")
        self.apply_tiled_button.setFixedHeight(36)
        self.apply_tiled_button.clicked.connect(lambda: on_apply_tiled_clicked(self))

        v.addWidget(props_bin)
        v.addWidget(self.apply_button)
        v.addWidget(self.apply_tiled_button)

        self.dock_props = QtWidgets.QDockWidget("Свойства Нода", self)
        self.dock_props.setWidget(props_wrap)
        self.addDockWidget(QtCore.Qt.DockWidgetArea.RightDockWidgetArea, self.dock_props)

    def _setup_menu(self):
        m = self.menuBar()

        proj = m.addMenu("Проект")
        proj.addAction("Новый Проект...").triggered.connect(lambda: on_new_project(self))
        proj.addAction("Открыть Проект...").triggered.connect(lambda: on_open_project(self))

        pipe = m.addMenu("Файл Пайплайна")
        pipe.addAction("Загрузить Пайплайн...").triggered.connect(lambda: on_load_pipeline(self))
        pipe.addAction("Сохранить Пайплайн...").triggered.connect(lambda: on_save_pipeline(self))
        pipe.addSeparator()
        pipe.addAction("Сгенерировать Мир...").triggered.connect(lambda: on_generate_world(self))
        pipe.addSeparator()
        pipe.addAction("Выход").triggered.connect(self.close)

        m.addMenu("Окна")  # задел на будущее

    # --------------------------- Проектные данные ------------------------------

    def get_project_data(self):
        """
        Возвращает dict из project.json текущего проекта,
        либо None, если проект ещё не открыт/создан.
        """
        if not self.current_project_path:
            return None
        try:
            with open(Path(self.current_project_path) / "project.json", "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            self.statusBar.showMessage(f"Ошибка чтения файла проекта: {e}", 5000)
            return None

    def _ensure_graph_focus(self):
        """Дать фокус именно viewer’у редактора графа, чтобы работал Delete."""
        viewer = getattr(self.graph, "widget", None) or getattr(self.graph, "viewer", None)
        if viewer is None:
            return
        viewer.setFocusPolicy(QtCore.Qt.FocusPolicy.StrongFocus)
        if not viewer.hasFocus():
            viewer.setFocus(QtCore.Qt.FocusReason.ActiveWindowFocusReason)



    def _delete_selected_nodes(self):
        # Трейс, чтобы видеть, что шорткат действительно сработал
        print("[TRACE/UI] delete pressed", flush=True)
        try:
            selected = list(self.graph.selected_nodes())
        except Exception:
            selected = []
        if not selected:
            return
        # Пытаемся удалить пачкой; если у твоей версии другой API — подстрахуемся
        if hasattr(self.graph, "delete_nodes"):
            try:
                self.graph.delete_nodes(selected)
                return
            except Exception as e:
                print(f"[TRACE/UI] delete_nodes(list) failed: {e}", flush=True)
        if hasattr(self.graph, "delete_selected_nodes"):
            try:
                self.graph.delete_selected_nodes()
                return
            except Exception as e:
                print(f"[TRACE/UI] delete_selected_nodes() failed: {e}", flush=True)
        # Жёсткий fallback — по одному
        for n in selected:
            try:
                self.graph.delete_nodes([n])
            except Exception:
                pass
