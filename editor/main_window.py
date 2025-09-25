# ==============================================================================
# Файл: editor/main_window.py
# ВЕРСИЯ 8.2: Стабильная одновкладочная версия со всеми исправлениями.
# ==============================================================================
import logging
from typing import cast

from PySide6 import QtWidgets, QtCore, QtGui
from NodeGraphQt import NodeGraph, BackdropNode
from PySide6.QtGui import QKeySequence


# --- Логика, вынесенная в другие модули ---
from .compute_manager import ComputeManager
from .actions.preset_actions import (
    load_preset_into_graph,
    handle_new_preset,
    handle_delete_preset,
)
from .actions.project_actions import on_save_project, load_project_data
from .actions.generation_actions import on_generate_world
from .actions.pipeline_actions import on_save_pipeline, on_load_pipeline
from .custom_graph import CustomNodeGraph

# --- UI компоненты ---
from .nodes.base_node import GeneratorNode
from .nodes.node_registry import register_all_nodes
from .preview_widget import Preview3DWidget
from .ui_panels.project_params_panel import create_project_params_dock
from .ui_panels.global_noise_panel import create_global_noise_dock
from .ui_panels.nodes_palette_panel import create_nodes_palette_dock
from .ui_panels.properties_panel import create_properties_dock
from .ui_panels.compute_panel import create_compute_dock
from .ui_panels.region_presets_panel import create_region_presets_dock

logger = logging.getLogger(__name__)


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, project_path: str):
        super().__init__()
        logger.info("Initializing MainWindow...")
        self.current_project_path = project_path

        self._init_ui_attributes()
        project_data = self.get_project_data()
        if not project_data:
            QtWidgets.QMessageBox.critical(self, "Ошибка проекта", "Не удалось загрузить данные.")
            QtCore.QTimer.singleShot(0, self.close)
            return

        self.compute_manager = ComputeManager(self)
        self.setWindowTitle("Редактор Миров")
        self.resize(1600, 900)
        self.setTabPosition(
            QtCore.Qt.DockWidgetArea.AllDockWidgetAreas,
            QtWidgets.QTabWidget.TabPosition.North,
        )

        self._setup_central_widget()
        self._setup_docks()
        self._setup_menu()
        self.setStatusBar(QtWidgets.QStatusBar())
        self._apply_project_to_ui(project_data)
        self._load_presets_list()
        self.statusBar().showMessage(f"Проект загружен: {project_path}", 5000)
        self._connect_signals()

    def _init_ui_attributes(self):
        self.graph = None
        self.preview_widget = Preview3DWidget()
        self.presets_list_widget = None
        self.dock_region_presets = self.dock_nodes = self.dock_props = None
        self.dock_project_params = self.dock_global_noise = None
        self.seed_input = self.global_x_offset_input = self.global_z_offset_input = None
        self.chunk_size_input = self.region_size_input = self.cell_size_input = None
        self.total_size_label = None
        self.gn_scale_input = self.gn_octaves_input = self.gn_amp_input = None
        self.gn_ridge_checkbox = None
        self.apply_button = self.apply_tiled_button = None
        self.wants_restart = False

    def _connect_signals(self):
        self.compute_manager.display_mesh.connect(self.preview_widget.update_mesh)
        self.compute_manager.display_tiled_mesh.connect(self.preview_widget.update_mesh)
        self.compute_manager.display_partial_tile.connect(self.preview_widget.on_tile_ready)
        self.compute_manager.display_status_message.connect(self.statusBar().showMessage)
        self.compute_manager.show_error_dialog.connect(
            lambda title, msg: QtWidgets.QMessageBox.critical(self, title, msg)
        )
        self.compute_manager.set_busy_mode.connect(self._set_ui_busy)
        self.apply_button.clicked.connect(self._on_apply_clicked)
        self.apply_tiled_button.clicked.connect(self._on_apply_tiled_clicked)
        self.presets_list_widget.currentItemChanged.connect(self.on_preset_selected)
        if self.graph:
            self.graph.property_changed.connect(self._on_node_property_changed)

    def get_active_graph(self) -> NodeGraph | None:
        return self.graph

    def _setup_central_widget(self):
        # Используем только кастомный граф
        self.graph = CustomNodeGraph()
        register_all_nodes(self.graph)

        graph_widget = self.graph.widget
        graph_widget.setObjectName("Основной граф 'Ландшафт'")
        graph_widget.setFocusPolicy(QtCore.Qt.FocusPolicy.StrongFocus)
        graph_widget.setFocus(QtCore.Qt.FocusReason.ActiveWindowFocusReason)

        # --- Привязка Delete к реальному QGraphicsView + локальная диагностика ---
        view = graph_widget.findChild(QtWidgets.QGraphicsView)
        if view is None:
            logger.warning("Graph view not found, binding shortcuts to graph_widget")
            view = graph_widget  # fallback

        def _do_delete():
            sel = [n.name() for n in self.graph.selected_nodes()]
            logger.debug("[DELETE] shortcut fired; selected=%s", sel)
            if sel:
                self.graph.delete_nodes(self.graph.selected_nodes())

        # Один набор хоткеев (без дубликатов и без QAction)
        del_sc = QtGui.QShortcut(QtGui.QKeySequence(QtCore.Qt.Key_Delete), view)
        del_sc.setContext(QtCore.Qt.ShortcutContext.WidgetShortcut)
        del_sc.activated.connect(_do_delete)

        back_sc = QtGui.QShortcut(QtGui.QKeySequence(QtCore.Qt.Key_Backspace), view)
        back_sc.setContext(QtCore.Qt.ShortcutContext.WidgetShortcut)
        back_sc.activated.connect(_do_delete)

        # Локальный шпион — чтобы видеть, доходят ли нажатия (не требует импортов)
        class _KeySpy(QtCore.QObject):
            def eventFilter(self, o, e):
                if e.type() == QtCore.QEvent.Type.KeyPress:
                    try:
                        key_name = QtCore.Qt.Key(e.key()).name
                    except Exception:
                        key_name = str(e.key())
                    logger.debug("[KEY on VIEW] %s (focus=%s)",
                                 key_name, QtWidgets.QApplication.focusWidget())
                return super().eventFilter(o, e)

        spy = _KeySpy(view)
        view.installEventFilter(spy)

        # Гарантируем фокус на канве после сборки UI
        view.setFocusPolicy(QtCore.Qt.FocusPolicy.StrongFocus)
        QtCore.QTimer.singleShot(0, view.setFocus)

        # --- Центральный сплиттер: превью сверху, граф снизу ---
        splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Vertical)
        splitter.addWidget(self.preview_widget)
        splitter.addWidget(cast(QtWidgets.QWidget, graph_widget))
        splitter.setSizes([400, 600])
        self.setCentralWidget(splitter)

    def _setup_docks(self):
        self.setDockNestingEnabled(True)
        create_region_presets_dock(self)
        create_project_params_dock(self)
        create_global_noise_dock(self)
        create_compute_dock(self)
        create_nodes_palette_dock(self)
        create_properties_dock(self)

        if self.graph:
            self.graph.node_selected.connect(self._on_node_selected)

        self.tabifyDockWidget(self.dock_region_presets, self.dock_nodes)
        self.tabifyDockWidget(self.dock_project_params, self.dock_global_noise)
        self.tabifyDockWidget(self.dock_global_noise, self.dock_props)

    def _set_ui_busy(self, busy: bool):
        self.apply_button.setEnabled(not busy)
        self.apply_tiled_button.setEnabled(not busy)

    def _on_apply_clicked(self):
        graph = self.get_active_graph()
        if not graph: return
        output_node = self._find_output_node(graph)
        if not output_node: return
        context = self._get_context_from_ui()
        self.compute_manager.start_single_compute(output_node, context)

    def _on_apply_tiled_clicked(self):
        graph = self.get_active_graph()
        if not graph: return
        output_node = self._find_output_node(graph)
        if not output_node: return
        context = self._get_context_from_ui()
        self.compute_manager.start_tiled_compute(output_node, context)

    def on_new_preset_clicked(self):
        handle_new_preset(self)

    def on_delete_preset_clicked(self):
        handle_delete_preset(self)

    def on_save_project(self):
        on_save_project(self)

    def _find_output_node(self, graph):
        nodes = list(graph.all_nodes())
        outs = [n for n in nodes if getattr(n, "NODE_NAME", "") == "Output"]
        if not outs:
            QtWidgets.QMessageBox.warning(self, "Ошибка графа", "В графе отсутствует нода 'Output'.")
            return None
        return outs[0]

    def _get_context_from_ui(self) -> dict:
        global_noise_params = {
            "scale_tiles": self.gn_scale_input.value(), "octaves": self.gn_octaves_input.value(),
            "amp_m": self.gn_amp_input.value(), "ridge": self.gn_ridge_checkbox.isChecked()
        }
        cs = int(self.chunk_size_input.value())
        rs = int(self.region_size_input.value())
        return {
            "cell_size": self.cell_size_input.value(), "seed": self.seed_input.value(),
            "global_x_offset": self.global_x_offset_input.value(), "global_z_offset": self.global_z_offset_input.value(),
            "chunk_size": cs, "region_size_in_chunks": rs, "global_noise": global_noise_params
        }

    def closeEvent(self, e):
        logger.info("Close event triggered.")
        super().closeEvent(e)

    def _setup_menu(self):
        m = self.menuBar()
        proj_menu = m.addMenu("Проект")
        def return_to_manager():
            self.wants_restart = True
            self.close()
        proj_menu.addAction("Сменить проект...").triggered.connect(return_to_manager)
        proj_menu.addSeparator()
        proj_menu.addAction("Сохранить Проект").triggered.connect(self.on_save_project)
        proj_menu.addSeparator()
        proj_menu.addAction("Сгенерировать Мир...").triggered.connect(lambda: on_generate_world(self))
        proj_menu.addSeparator()
        proj_menu.addAction("Выход").triggered.connect(self.close)
        presets_menu = m.addMenu("Пресеты")
        presets_menu.addAction("Загрузить Пресет").triggered.connect(lambda: on_load_pipeline(self))
        presets_menu.addAction("Сохранить Пресет...").triggered.connect(lambda: on_save_pipeline(self))

    def get_project_data(self) -> dict | None:
        data = load_project_data(self.current_project_path)
        if data is None:
            self.statusBar().showMessage("Ошибка чтения файла проекта!", 5000)
        return data

    def _apply_project_to_ui(self, data: dict) -> None:
        self.seed_input.setValue(int(data.get("seed", 1)))
        self.chunk_size_input.setValue(int(data.get("chunk_size", 128)))
        self.region_size_input.setValue(int(data.get("region_size_in_chunks", 4)))
        self.cell_size_input.setValue(float(data.get("cell_size", 1.0)))
        self.global_x_offset_input.setValue(int(data.get("global_x_offset", 0)))
        self.global_z_offset_input.setValue(int(data.get("global_z_offset", 0)))
        noise_data = data.get("global_noise", {})
        self.gn_scale_input.setValue(float(noise_data.get("scale_tiles", 6000.0)))
        self.gn_octaves_input.setValue(int(noise_data.get("octaves", 3)))
        self.gn_amp_input.setValue(float(noise_data.get("amp_m", 400.0)))
        self.gn_ridge_checkbox.setChecked(bool(noise_data.get("ridge", False)))
        project_name = data.get("project_name", "Безымянный проект")
        self.setWindowTitle(f"Редактор Миров — [{project_name}]")

    def _load_presets_list(self):
        self.presets_list_widget.currentItemChanged.disconnect(self.on_preset_selected)
        self.presets_list_widget.clear()
        project_data = self.get_project_data()
        if not project_data: return
        presets = project_data.get("region_presets", {})
        active_preset_name = project_data.get("active_preset_name", "")
        item_to_select = None
        for name in presets.keys():
            item = QtWidgets.QListWidgetItem(name)
            self.presets_list_widget.addItem(item)
            if name == active_preset_name:
                item_to_select = item
        self.presets_list_widget.currentItemChanged.connect(self.on_preset_selected)
        if item_to_select:
            self.presets_list_widget.setCurrentItem(item_to_select)
        elif self.presets_list_widget.count() > 0:
            self.presets_list_widget.setCurrentRow(0)

    def _update_preset_list_font(self):
        project_data = self.get_project_data()
        if not project_data: return
        active_preset_name = project_data.get("active_preset_name", "")
        for i in range(self.presets_list_widget.count()):
            item = self.presets_list_widget.item(i)
            font = item.font()
            font.setBold(item.text() == active_preset_name)
            item.setFont(font)

    def on_preset_selected(self, current_item: QtWidgets.QListWidgetItem):
        if not current_item: return
        preset_name = current_item.text()
        project_data = self.get_project_data()
        if not project_data: return
        project_data["active_preset_name"] = preset_name
        self._update_preset_list_font()
        preset_info = project_data.get("region_presets", {}).get(preset_name)
        if not preset_info:
            logger.error(f"Preset '{preset_name}' not found in project.json")
            return
        load_preset_into_graph(self, preset_info)
        self.statusBar().showMessage(f"Пресет '{preset_name}' загружен", 4000)

    def _on_node_selected(self, node):
        if not self.dock_props: return
        props_bin = self.dock_props.widget()
        if not props_bin: return
        tab_widget = props_bin.findChild(QtWidgets.QTabWidget)
        if not tab_widget: return
        for i in range(tab_widget.count()):
            if tab_widget.tabText(i) == "Описание":
                tab_widget.removeTab(i)
                break
        if isinstance(node, GeneratorNode):
            desc_widget = QtWidgets.QWidget()
            layout = QtWidgets.QVBoxLayout(desc_widget)
            text_label = QtWidgets.QLabel(node.get_description())
            text_label.setWordWrap(True)
            text_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignTop)
            layout.addWidget(text_label)
            tab_widget.addTab(desc_widget, "Описание")

    def _on_node_property_changed(self, node, prop_name, prop_value):
        if isinstance(node, GeneratorNode):
            node.mark_dirty()

