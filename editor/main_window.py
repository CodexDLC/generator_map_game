# ==============================================================================
# Файл: editor/main_window.py
# ВЕРСИЯ 9.0: Распил по модулям (central_graph, menu, shortcuts, signals, binding, queries)
# ==============================================================================
import logging


from PySide6 import QtWidgets, QtCore
from NodeGraphQt import NodeGraph

from .actions.close_actions import handle_close_event
from .compute_manager import ComputeManager
from .actions.preset_actions import (
    load_preset_into_graph,
    handle_new_preset,
    handle_delete_preset,
    handle_save_active_preset,
)
from .actions.project_actions import on_save_project, load_project_data
from .actions.generation_actions import on_generate_world
from .actions.pipeline_actions import on_save_pipeline, on_load_pipeline
from .graph.queries import require_output_node

# --- UI компоненты ---
from .nodes.base_node import GeneratorNode
from .nodes.node_registry import register_all_nodes
from .preview_widget import Preview3DWidget
from .ui_panels.central_graph import setup_central_graph_ui
from .ui_panels.menu import build_menu
from .ui_panels.project_binding import apply_project_to_ui, collect_context_from_ui
from .ui_panels.project_params_panel import create_project_params_dock
from .ui_panels.global_noise_panel import create_global_noise_dock
from .ui_panels.nodes_palette_panel import create_nodes_palette_dock
from .ui_panels.properties_panel import create_properties_dock
from .ui_panels.accordion_properties import AccordionProperties
from .ui_panels.compute_panel import create_compute_dock
from .ui_panels.region_presets_panel import create_region_presets_dock
from .ui_panels.shortcuts import install_global_shortcuts

# --- Новые хелперы ---

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

        # Центральная часть (граф + превью)
        self._setup_central_widget()
        # Док-панели
        self._setup_docks()
        # Меню и хоткеи
        build_menu(self)
        install_global_shortcuts(self)

        self.setStatusBar(QtWidgets.QStatusBar())

        # Привязка данных проекта к UI
        apply_project_to_ui(self, project_data)
        self._load_presets_list()
        self.statusBar().showMessage(f"Проект загружен: {project_path}", 5000)

        # Сигналы
        self._connect_signals()

    # -- Инициализация простых атрибутов --
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

    # -- Вспомогательные обёртки для меню (чтобы ui/menu.py не тянул actions) --
    def _return_to_manager(self):
        self.wants_restart = True
        self.close()

    def on_generate_world_menu(self):
        on_generate_world(self)

    def on_load_pipeline_menu(self):
        on_load_pipeline(self)

    def on_save_pipeline_menu(self):
        on_save_pipeline(self)

    # -- Graph getter для PropertiesBinWidget --
    def get_active_graph(self) -> NodeGraph | None:
        return self.graph

    # -- Центральная часть --
    def _setup_central_widget(self):
        setup_central_graph_ui(self)

    # -- Док-панели (оставили как было) --

    def _setup_docks(self):
        self.setDockNestingEnabled(True)

        # 1. Создаем все панели, КРОМЕ старой панели свойств
        create_region_presets_dock(self)
        create_project_params_dock(self)
        create_global_noise_dock(self)
        create_compute_dock(self)
        create_nodes_palette_dock(self)

        # 2. Создаем и добавляем ТОЛЬКО новую панель-аккордеон
        acc_dock = QtWidgets.QDockWidget("Свойства", self)
        acc_dock.setObjectName("Панель 'Свойства'")
        self.acc_props = AccordionProperties(graph=self.graph, parent=acc_dock)
        acc_dock.setWidget(self.acc_props)
        self.addDockWidget(QtCore.Qt.DockWidgetArea.RightDockWidgetArea, acc_dock)

        # 3. Сохраняем ссылку на новую панель в self.dock_props для группировки
        #    (Это нужно, чтобы tabifyDockWidget работал как раньше)
        self.dock_props = acc_dock

        # 4. Подписываемся на сигнал выбора ноды, если нужно (например, для вкладки "Описание")
        if self.graph:
            # AccordionProperties уже сам слушает этот сигнал для обновления,
            # но этот connect может быть нужен для других кастомных действий.
            self.graph.node_selected.connect(self._on_node_selected)

        # 5. Группируем док-панели во вкладки, как и было
        self.tabifyDockWidget(self.dock_region_presets, self.dock_nodes)
        self.tabifyDockWidget(self.dock_project_params, self.dock_global_noise)
        self.tabifyDockWidget(self.dock_global_noise, self.dock_props)

    # -- UI busy state --
    def _set_ui_busy(self, busy: bool):
        """Включает/выключает состояние занятости без тайловой кнопки."""
        if getattr(self, "apply_button", None):
            self.apply_button.setEnabled(not busy)
        atb = getattr(self, "apply_tiled_button", None)
        if atb:  # если вдруг живёт где-то в старом лэйауте
            atb.setEnabled(False)
            atb.setVisible(False)

    # -- Запуски вычислений --
    def _on_apply_clicked(self):
        graph = self.get_active_graph()
        if not graph:
            return
        output_node = require_output_node(self, graph)
        if not output_node:
            return
        context = collect_context_from_ui(self)
        self.compute_manager.start_single_compute(output_node, context)

    def _on_apply_tiled_clicked(self):
        """Совместимость: тайлов больше нет — запускаем обычный расчёт."""
        self._on_apply_clicked()

    # -- Делегаты из меню --
    def on_new_preset_clicked(self):
        handle_new_preset(self)

    def on_delete_preset_clicked(self):
        handle_delete_preset(self)

    def on_save_active_preset_clicked(self):
        handle_save_active_preset(self)

    def on_save_project(self):
        on_save_project(self)

    # -- Проектные данные --
    def get_project_data(self) -> dict | None:
        data = load_project_data(self.current_project_path)
        if data is None:
            self.statusBar().showMessage("Ошибка чтения файла проекта!", 5000)
        return data

    # -- Пресеты списка --
    def _load_presets_list(self):
        self.presets_list_widget.currentItemChanged.disconnect(self.on_preset_selected)
        self.presets_list_widget.clear()
        project_data = self.get_project_data()
        if not project_data:
            return
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
        if not project_data:
            return
        active_preset_name = project_data.get("active_preset_name", "")
        for i in range(self.presets_list_widget.count()):
            item = self.presets_list_widget.item(i)
            font = item.font()
            font.setBold(item.text() == active_preset_name)
            item.setFont(font)

    def _connect_signals(self):
        """
        Склеивает все сигналы UI/воркеров. Версия без тайловых сигналов.
        """
        cm = self.compute_manager

        # --- Compute → Preview/Status ---

        # 1. Временно отключаем старое подключение
        cm.display_mesh.connect(
            self.preview_widget.update_mesh,
            type=QtCore.Qt.ConnectionType.QueuedConnection
        )

        cm.display_status_message.connect(self.statusBar().showMessage)
        cm.show_error_dialog.connect(
            lambda title, msg: QtWidgets.QMessageBox.critical(self, title, msg)
        )
        cm.set_busy_mode.connect(self._set_ui_busy)

        # --- Кнопки APPLY ---
        self.apply_button.clicked.connect(self._on_apply_clicked)

        # если где-то ещё создаётся apply_tiled_button — безопасно игнорируем
        if getattr(self, "apply_tiled_button", None):
            try:
                self.apply_tiled_button.clicked.disconnect()
            except Exception:
                pass
            self.apply_tiled_button.setEnabled(False)
            self.apply_tiled_button.setVisible(False)

        # --- Список пресетов ---
        if self.presets_list_widget is not None:
            self.presets_list_widget.currentItemChanged.connect(self.on_preset_selected)

        # --- Граф: реагируем на изменение свойств, чтобы помечать ноды грязными ---
        if self.graph is not None:
            try:
                self.graph.property_changed.connect(self._on_node_property_changed)
            except Exception:
                # На некоторых версиях NodeGraphQt сигнал может называться иначе — не падаем.
                pass

    def on_preset_selected(self, current_item: QtWidgets.QListWidgetItem):
        if not current_item:
            return
        preset_name = current_item.text()
        project_data = self.get_project_data()
        if not project_data:
            return
        project_data["active_preset_name"] = preset_name
        self._update_preset_list_font()
        preset_info = project_data.get("region_presets", {}).get(preset_name)
        if not preset_info:
            logger.error(f"Preset '{preset_name}' not found in project.json")
            return
        load_preset_into_graph(self, preset_info)
        self.statusBar().showMessage(f"Пресет '{preset_name}' загружен", 4000)

    # -- Свойства/описание ноды --
    def _on_node_selected(self, node):
        """
        Вызывается при выборе ноды.
        Теперь отвечает ТОЛЬКО за кастомную вкладку "Описание".
        """
        # Эта проверка остается на всякий случай
        if not self.dock_props:
            return

        props_bin = self.dock_props.widget()
        if not props_bin:
            return

        # Наша кастомная логика для вкладки "Описание"
        # Она не мешает работе виджета
        tab_widget = props_bin.findChild(QtWidgets.QTabWidget)
        if not tab_widget:
            return
        # Сначала удаляем старую вкладку "Описание", если она есть
        for i in range(tab_widget.count()):
            if tab_widget.tabText(i) == "Описание":
                tab_widget.removeTab(i)
                break

        # Если выбрана наша нода, добавляем для нее "Описание"
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

    # -- Закрытие --
    def closeEvent(self, event):
        """Перехватывает закрытие и передает управление в close_actions."""
        # Вся сложная логика теперь в отдельном файле
        handle_close_event(self, event)

        # Если событие было принято (не отменено), корректно завершаем фоновые процессы
        if event.isAccepted():
            try:
                if hasattr(self, "compute_manager") and self.compute_manager:
                    self.compute_manager.shutdown()
            finally:
                super().closeEvent(event)
        else:
            # Если пользователь нажал "Отмена", просто игнорируем событие
            super().closeEvent(event)

    def set_sun(self, azimuth_deg=315.0, altitude_deg=45.0):
        # переводим в вектор
        import math
        az = math.radians(azimuth_deg)
        alt = math.radians(altitude_deg)
        lx = math.cos(alt) * math.cos(az)
        ly = math.sin(alt)
        lz = math.cos(alt) * math.sin(az)
        for vis in self._tiles.values():
            if hasattr(vis, "_hm_light"):
                vis._hm_light.set_light_dir((lx, ly, lz))
        self.canvas.update()
        
        
    # def _on_display_impostor(self, height_map, cell_size, *rest):
    # # можно подкрутить параметры тут
    #     self.preview_widget.update_impostor(
    #         height_map,
    #         cell_size,
    #         z_scale=1.0,
    #         light_dir=(0.4, 0.8, 0.4),
    #     )