# ==============================================================================
# Файл: editor/main_window.py
# ВЕРСИЯ 2.4: Добавлено удаление нодов по клавише Delete и через контекстное меню.
# ==============================================================================
import numpy as np
# ИЗМЕНЕНИЕ: Добавляем QtGui для QAction
from PySide6 import QtWidgets, QtCore, QtGui
from NodeGraphQt import NodeGraph, PropertiesBinWidget, NodesTreeWidget

# ... (остальные импорты без изменений) ...
from .nodes.noise_node import NoiseNode
from .nodes.output_node import OutputNode
from .graph_runner import compute_graph
from .preview_widget import Preview3DWidget


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Редактор пресетов")
        self.resize(1600, 900)
        self.graph = NodeGraph()

        # --- ИЗМЕНЕНИЕ: Интегрируем ваш код для удаления нодов ---

        # Получаем виджет графа для удобства
        graph_widget = self.graph.widget

        # 1. Устанавливаем политику фокуса, чтобы виджет мог "ловить" нажатия клавиш
        graph_widget.setFocusPolicy(QtCore.Qt.FocusPolicy.StrongFocus)

        # 2. Создаем функцию для удаления выделенных элементов
        def _delete_selected_items():
            """Удаляет выделенные ноды или, если их нет, выделенные соединения."""
            selected_nodes = self.graph.selected_nodes()
            if selected_nodes:
                self.graph.delete_nodes(selected_nodes)
            else:
                self.graph.delete_pipes(self.graph.selected_pipes())

        # 3. Создаем "действие" (Action) и привязываем к нему хоткеи
        delete_action = QtGui.QAction("Удалить", self)
        # Привязываем клавиши Delete и Backspace
        delete_action.setShortcuts([QtGui.QKeySequence.StandardKey.Delete, QtCore.Qt.Key.Key_Backspace])
        delete_action.triggered.connect(_delete_selected_items)
        self.addAction(delete_action)

        # 4. Добавляем это же действие в контекстное меню (вызывается по правому клику)
        graph_widget.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.ActionsContextMenu)
        graph_widget.addAction(delete_action)

        # --- КОНЕЦ ИЗМЕНЕНИЙ ---

        # ... (остальной код __init__ без изменений) ...
        central_container = QtWidgets.QWidget()
        central_layout = QtWidgets.QVBoxLayout(central_container)
        central_layout.setContentsMargins(0, 0, 0, 0)
        central_layout.setSpacing(0)
        splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Vertical)
        self.preview_widget = Preview3DWidget()
        self.preview_widget.setMinimumHeight(200)
        splitter.addWidget(self.preview_widget)
        splitter.addWidget(graph_widget)  # Используем нашу переменную
        splitter.setSizes([400, 600])
        central_layout.addWidget(splitter)
        self.setCentralWidget(central_container)

        self._register_nodes()
        self._setup_docks()
        self._setup_menu()

    # ... (остальные методы без изменений) ...
    def _setup_docks(self):
        self.setDockNestingEnabled(True)

        # Палитра нодов (слева)
        nodes_tree = NodesTreeWidget(node_graph=self.graph)
        nodes_dock = QtWidgets.QDockWidget("Палитра Нодов", self)
        nodes_dock.setWidget(nodes_tree)
        self.addDockWidget(QtCore.Qt.DockWidgetArea.LeftDockWidgetArea, nodes_dock)

        # Контейнер для настроек
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
        settings_layout.addRow("Map Size (px):", self.size_input)
        settings_layout.addRow("Cell Size (m):", self.cell_size_input)
        settings_layout.addRow("World Seed:", self.seed_input)
        settings_dock = QtWidgets.QDockWidget("Настройки Генерации", self)
        settings_dock.setWidget(settings_container)
        self.addDockWidget(QtCore.Qt.DockWidgetArea.RightDockWidgetArea, settings_dock)

        # Инспектор свойств (справа, под настройками)
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
        """Создает верхнее меню."""
        menu_bar = self.menuBar()
        file_menu = menu_bar.addMenu("Файл")
        file_menu.addAction("Загрузить пресет...")
        file_menu.addAction("Сохранить пресет...")
        file_menu.addSeparator()
        file_menu.addAction("Сгенерировать Мир...")
        file_menu.addSeparator()
        file_menu.addAction("Выход")
        menu_bar.addMenu("Окна")

    def _register_nodes(self):
        """Регистрирует все наши кастомные ноды в графе."""
        self.graph.register_node(NoiseNode)
        self.graph.register_node(OutputNode)

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