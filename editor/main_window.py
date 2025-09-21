# ==============================================================================
# Файл: editor/main_window.py
# ВЕРСИЯ 5.0 (Рефакторинг завершен): Вся логика вынесена в 'actions'.
# ==============================================================================
import json
from pathlib import Path

from PySide6 import QtWidgets, QtCore, QtGui
from NodeGraphQt import NodeGraph, PropertiesBinWidget, NodesTreeWidget

from .actions.generation_actions import on_generate_world
# --- НАЧАЛО ИЗМЕНЕНИЙ: Импортируем всю логику извне ---
from .actions.project_actions import on_new_project, on_open_project
from .actions.pipeline_actions import on_save_pipeline, on_load_pipeline
from .actions.compute_actions import on_apply_clicked
# --- КОНЕЦ ИЗМЕНЕНИЙ ---

from .nodes.node_registry import register_all_nodes
from .preview_widget import Preview3DWidget


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Редактор Миров")
        self.resize(1600, 900)
        self.graph = NodeGraph()
        self.current_project_path = None

        self.thread = None
        self.worker = None

        graph_widget = self.graph.widget
        graph_widget.setFocusPolicy(QtCore.Qt.FocusPolicy.StrongFocus)

        def _delete_selected_items():
            selected_nodes = self.graph.selected_nodes()
            if selected_nodes:
                self.graph.delete_nodes(selected_nodes)
            else:
                self.graph.delete_pipes(self.graph.selected_pipes())

        delete_action = QtGui.QAction("Удалить", self)
        delete_action.setShortcuts([QtGui.QKeySequence.StandardKey.Delete, QtCore.Qt.Key.Key_Backspace])
        delete_action.triggered.connect(_delete_selected_items)
        self.addAction(delete_action)
        graph_widget.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.ActionsContextMenu)
        graph_widget.addAction(delete_action)

        central_container = QtWidgets.QWidget()
        central_layout = QtWidgets.QVBoxLayout(central_container)
        central_layout.setContentsMargins(0, 0, 0, 0)
        central_layout.setSpacing(0)
        splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Vertical)
        self.preview_widget = Preview3DWidget()
        self.preview_widget.setMinimumHeight(200)
        splitter.addWidget(self.preview_widget)
        splitter.addWidget(graph_widget)
        splitter.setSizes([400, 600])
        central_layout.addWidget(splitter)
        self.setCentralWidget(central_container)

        self._register_nodes()
        self._setup_docks()
        self._setup_menu()

    def _setup_docks(self):
        self.setDockNestingEnabled(True)

        nodes_tree = NodesTreeWidget(node_graph=self.graph)
        nodes_dock = QtWidgets.QDockWidget("Палитра Нодов", self)
        nodes_dock.setWidget(nodes_tree)
        self.addDockWidget(QtCore.Qt.DockWidgetArea.LeftDockWidgetArea, nodes_dock)

        settings_container = QtWidgets.QWidget()
        settings_layout = QtWidgets.QFormLayout(settings_container)
        self.seed_input = QtWidgets.QSpinBox()
        self.seed_input.setRange(0, 999999)
        self.seed_input.setValue(12345)
        settings_layout.addRow("World Seed:", self.seed_input)
        self.global_x_offset_input = QtWidgets.QSpinBox()
        self.global_x_offset_input.setRange(-999999, 999999)
        self.global_x_offset_input.setValue(0)
        self.global_x_offset_input.setSingleStep(512)
        settings_layout.addRow("Global X Offset:", self.global_x_offset_input)
        self.global_z_offset_input = QtWidgets.QSpinBox()
        self.global_z_offset_input.setRange(-999999, 999999)
        self.global_z_offset_input.setValue(0)
        self.global_z_offset_input.setSingleStep(512)
        settings_layout.addRow("Global Z Offset:", self.global_z_offset_input)

        # Новое поле для размера чанка
        self.chunk_size_input = QtWidgets.QSpinBox()
        self.chunk_size_input.setRange(64, 1024)
        self.chunk_size_input.setValue(512)
        settings_layout.addRow("Chunk Size (px):", self.chunk_size_input)

        # Новое поле для размера региона в чанках
        self.region_size_input = QtWidgets.QSpinBox()
        self.region_size_input.setRange(1, 32)
        self.region_size_input.setValue(1)
        settings_layout.addRow("Region Size (chunks):", self.region_size_input)

        self.cell_size_input = QtWidgets.QDoubleSpinBox()
        self.cell_size_input.setRange(0.1, 10.0)
        self.cell_size_input.setValue(1.0)
        self.cell_size_input.setDecimals(2)
        self.cell_size_input.setSingleStep(0.1)
        settings_layout.addRow("Cell Size (m):", self.cell_size_input)

        # --- СТРОКА С ОШИБКОЙ БЫЛА ЗДЕСЬ И ТЕПЕРЬ УДАЛЕНА ---

        settings_dock = QtWidgets.QDockWidget("Настройки Визора", self)
        settings_dock.setWidget(settings_container)
        self.addDockWidget(QtCore.Qt.DockWidgetArea.RightDockWidgetArea, settings_dock)

        props_bin = PropertiesBinWidget(node_graph=self.graph)
        props_container = QtWidgets.QWidget()
        props_layout = QtWidgets.QVBoxLayout(props_container)
        props_layout.setContentsMargins(0, 0, 0, 0)
        self.apply_button = QtWidgets.QPushButton("APPLY")
        self.apply_button.setFixedHeight(40)
        self.apply_button.clicked.connect(lambda: on_apply_clicked(self))
        props_layout.addWidget(props_bin)
        props_layout.addWidget(self.apply_button)
        props_dock = QtWidgets.QDockWidget("Свойства Нода", self)
        props_dock.setWidget(props_container)
        self.addDockWidget(QtCore.Qt.DockWidgetArea.RightDockWidgetArea, props_dock)

        self.statusBar = QtWidgets.QStatusBar()
        self.setStatusBar(self.statusBar)

    def _setup_menu(self):
        menu_bar = self.menuBar()

        project_menu = menu_bar.addMenu("Проект")
        new_project_action = project_menu.addAction("Новый Проект...")
        new_project_action.triggered.connect(lambda: on_new_project(self))
        open_project_action = project_menu.addAction("Открыть Проект...")
        open_project_action.triggered.connect(lambda: on_open_project(self))

        file_menu = menu_bar.addMenu("Файл Пайплайна")
        load_action = file_menu.addAction("Загрузить Пайплайн...")
        load_action.triggered.connect(lambda: on_load_pipeline(self))
        save_action = file_menu.addAction("Сохранить Пайплайн...")
        save_action.triggered.connect(lambda: on_save_pipeline(self))

        file_menu.addSeparator()
        generate_action = file_menu.addAction("Сгенерировать Мир...")
        generate_action.triggered.connect(lambda: on_generate_world(self))
        file_menu.addSeparator()

        exit_action = file_menu.addAction("Выход")
        exit_action.triggered.connect(self.close)

        menu_bar.addMenu("Окна")

    def _register_nodes(self):
        register_all_nodes(self.graph)


    def get_project_data(self):
        """Читает и возвращает данные из текущего project.json"""
        if not self.current_project_path:
            return None
        try:
            with open(Path(self.current_project_path) / "project.json", 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            self.statusBar.showMessage(f"Ошибка чтения файла проекта: {e}", 5000)
            return None