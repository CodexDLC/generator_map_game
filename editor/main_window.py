# ==============================================================================
# Файл: editor/main_window.py
# ВЕРСИЯ 3.0: Реализована архитектура с пайплайнами. Добавлено сохранение/загрузка.
# ==============================================================================
import json
import numpy as np
from PySide6 import QtWidgets, QtCore, QtGui
from NodeGraphQt import NodeGraph, PropertiesBinWidget, NodesTreeWidget

from .nodes.noise_node import NoiseNode
from .nodes.output_node import OutputNode
from .graph_runner import compute_graph
from .preview_widget import Preview3DWidget


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Редактор Пайплайнов Генерации")
        self.resize(1600, 900)
        self.graph = NodeGraph()

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

        # ИЗМЕНЕНИЕ: Переименовываем панель
        settings_container = QtWidgets.QWidget()
        settings_layout = QtWidgets.QFormLayout(settings_container)
        self.size_input = QtWidgets.QSpinBox()
        self.size_input.setRange(64, 4096);
        self.size_input.setValue(512)
        self.cell_size_input = QtWidgets.QDoubleSpinBox()
        self.cell_size_input.setRange(0.1, 10.0);
        self.cell_size_input.setValue(1.0)
        self.cell_size_input.setDecimals(2);
        self.cell_size_input.setSingleStep(0.1)
        self.seed_input = QtWidgets.QSpinBox()
        self.seed_input.setRange(0, 99999);
        self.seed_input.setValue(12345)
        settings_layout.addRow("Preview Size (px):", self.size_input)
        settings_layout.addRow("Cell Size (m):", self.cell_size_input)
        settings_layout.addRow("Preview Seed:", self.seed_input)
        # ИЗМЕНЕНИЕ: Новый заголовок
        settings_dock = QtWidgets.QDockWidget("Настройки Предпросмотра", self)
        settings_dock.setWidget(settings_container)
        self.addDockWidget(QtCore.Qt.DockWidgetArea.RightDockWidgetArea, settings_dock)

        props_bin = PropertiesBinWidget(node_graph=self.graph)
        props_container = QtWidgets.QWidget()
        props_layout = QtWidgets.QVBoxLayout(props_container)
        props_layout.setContentsMargins(0, 0, 0, 0)
        self.apply_button = QtWidgets.QPushButton("APPLY")
        self.apply_button.setFixedHeight(40)
        self.apply_button.clicked.connect(self._on_apply_clicked)
        props_layout.addWidget(props_bin)
        props_layout.addWidget(self.apply_button)
        props_dock = QtWidgets.QDockWidget("Свойства Нода", self)
        props_dock.setWidget(props_container)
        self.addDockWidget(QtCore.Qt.DockWidgetArea.RightDockWidgetArea, props_dock)

        self.statusBar = QtWidgets.QStatusBar()
        self.setStatusBar(self.statusBar)

    def _setup_menu(self):
        menu_bar = self.menuBar()
        file_menu = menu_bar.addMenu("Файл")

        # ИЗМЕНЕНИЕ: Переименовываем и подключаем действия
        load_action = file_menu.addAction("Загрузить Пайплайн...")
        load_action.triggered.connect(self._on_load_pipeline)

        save_action = file_menu.addAction("Сохранить Пайплайн...")
        save_action.triggered.connect(self._on_save_pipeline)

        file_menu.addSeparator()
        file_menu.addAction("Сгенерировать Мир...")
        file_menu.addSeparator()

        exit_action = file_menu.addAction("Выход")
        exit_action.triggered.connect(self.close)

        menu_bar.addMenu("Окна")

    def _register_nodes(self):
        self.graph.register_node(NoiseNode)
        self.graph.register_node(OutputNode)

    # --- НОВЫЙ МЕТОД: Логика сохранения ---
    def _on_save_pipeline(self):
        file_path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Сохранить файл пайплайна", "", "JSON Files (*.json)"
        )
        if not file_path:
            return

        try:
            # Встроенная функция библиотеки для сериализации графа
            graph_data = self.graph.serialize_session()
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(graph_data, f, indent=2, ensure_ascii=False)
            self.statusBar.showMessage(f"Пайплайн успешно сохранен: {file_path}", 5000)
            print(f"Pipeline saved to: {file_path}")
        except Exception as e:
            self.statusBar.showMessage(f"Ошибка сохранения: {e}", 5000)
            print(f"ERROR saving pipeline: {e}")

    # --- НОВЫЙ МЕТОД: Логика загрузки ---
    def _on_load_pipeline(self):
        file_path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Загрузить файл пайплайна", "", "JSON Files (*.json)"
        )
        if not file_path:
            return

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                graph_data = json.load(f)

            # Очищаем текущую сцену
            self.graph.clear_session()
            # Загружаем граф из данных
            self.graph.deserialize_session(graph_data)

            self.statusBar.showMessage(f"Пайплайн успешно загружен: {file_path}", 5000)
            print(f"Pipeline loaded from: {file_path}")
        except Exception as e:
            self.statusBar.showMessage(f"Ошибка загрузки: {e}", 5000)
            print(f"ERROR loading pipeline: {e}")

    def _on_apply_clicked(self):
        print("\n[MainWindow] === APPLY CLICKED ===")
        self.statusBar.showMessage("Вычисление графа...")
        size = self.size_input.value()
        cell_size = self.cell_size_input.value()
        px_coords_x = np.arange(size, dtype=np.float32)
        px_coords_z = np.arange(size, dtype=np.float32)
        x_coords, z_coords = np.meshgrid(px_coords_x, px_coords_z)
        context = {
            "main_heightmap": np.zeros((size, size), dtype=np.float32),
            "x_coords": x_coords,
            "z_coords": z_coords,
            "cell_size": cell_size,
            "seed": self.seed_input.value()
        }
        result_map, message = compute_graph(self.graph, context)
        self.statusBar.showMessage(message)
        if result_map is not None:
            print(f"Результат получен! Средняя высота: {result_map.mean():.2f}")
            self.preview_widget.update_mesh(result_map, cell_size)
        else:
            print(f"Вычисление не удалось.")